"""Readiness, version comparison and scoped clinician handoffs."""
import json
import re
from collections import defaultdict

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from .documents import FIELDS, digest
from .models import Case, DocumentTemplate, ReviewTask, unseal
from .privacy import redact
from .views import api, audit, body, case_for, error, source_json


def has_fact(value):
    return bool(value.strip()) and not value.strip().lower().startswith('not recorded')


def source_changes(case, sources):
    approval = case.events.filter(action='draft_approved').order_by('-at').first()
    if not approval:
        return None
    draft = case.drafts.filter(id=approval.detail['draft_id']).first()
    if not draft:
        return None
    revision = approval.detail['revision']
    version = draft.versions.filter(revision=revision).first()
    if version is None and revision != draft.revision:
        return None
    snapshot = unseal(version.payload if version else draft.payload)
    if digest(snapshot) != approval.detail.get('hash'):
        return None
    before = snapshot['case_snapshot'].get('facts', {})
    after = unseal(case.payload).get('facts', {})
    baseline = snapshot['references']
    accepted = {s['id']: s for s in sources if s['status'] == 'accepted'}
    return {
        'approved_at': approval.at.isoformat(),
        'fields': [FIELDS[k] for k in FIELDS if before.get(k, '') != after.get(k, '')],
        'added': [s['title'] for k, s in accepted.items() if k not in baseline],
        'changed': [s['title'] for k, s in accepted.items()
                    if k in baseline and (s['text'], s['title']) != (baseline[k]['text'], baseline[k]['title'])],
        'removed': [s['title'] for k, s in baseline.items()
                    if not k.startswith('snapshot:') and k not in accepted],
        'stale_drafts': sum(unseal(d.payload)['case_revision'] != case.revision for d in case.drafts.all()),
    }


def record_differences(sources):
    # Compare explicit entries for the same documentation date. Preserve literal values.
    pattern = re.compile(r'(?im)^\s*(?:recorded )?(stage|treatment status|appointment date|referral date)\s*[:=]\s*([^\n;]+)')
    groups = defaultdict(list)
    for source in sources:
        if source['status'] != 'accepted' or not source.get('date'):
            continue
        for match in pattern.finditer(source['text']):
            key, value = match.groups()
            groups[key.lower(), source['date']].append({
                'id': source['id'], 'title': source['title'], 'value': value.strip(),
            })
    return [
        {'label': label.title(), 'date': date, 'sources': entries}
        for (label, date), entries in groups.items()
        if len({entry['id'] for entry in entries}) > 1
        and len({entry['value'].casefold() for entry in entries}) > 1
    ]


@api(['GET'])
def case_workflow(request, id):
    case = case_for(request, id)
    sources = [source_json(s) for s in case.sources.order_by('created_at')]
    facts = unseal(case.payload)
    pending = sum(s['status'] == 'pending' for s in sources)
    from .quality import flags
    differences = [f for f in flags(facts, sources) if f['kind'] == 'wording_difference']
    return JsonResponse({
        'fields': FIELDS,
        'readiness': {k: 'missing' if not has_fact(facts.get('facts', {}).get(k, ''))
                      else 'needs_review' if (not facts.get('confirmed') or pending
                                              or any(f['field'] == k for f in differences))
                      else 'confirmed' for k in FIELDS},
        'pending_sources': pending,
        'record_differences': record_differences(sources),
        'differences': [{**f, 'source': next(s for s in sources if s['id'] == f['source_id']),
                         'case_value': facts['facts'].get(f['field'], '')} for f in differences],
        'changes': source_changes(case, sources),
        'reviews': [task_summary(t) for t in case.review_tasks.select_related('reviewer').order_by('-updated_at')[:20]],
    })


def task_summary(task):
    return {'id': task.id, 'case_alias': task.case.alias, 'revision': task.case_revision,
            'reviewer': task.reviewer.username, 'status': task.status,
            'stale': task.case_revision != task.case.revision}


@api(['GET'])
def review_queue(request):
    tasks = ReviewTask.objects.filter(reviewer=request.user, case__is_synthetic=True)
    return JsonResponse({'reviews': [task_summary(t) for t in tasks.select_related('case', 'reviewer').order_by('-updated_at')[:50]]})


@api(['POST'])
def assign_review(request, id):
    data = body(request)
    username = data.get('reviewer')
    if not isinstance(username, str) or not username.strip() or len(username) > 150:
        return error('Enter the reviewer’s workspace username.')
    with transaction.atomic():
        case = case_for(request, id, True)
        if data.get('revision') != case.revision:
            return error('Case changed. Reload before assigning.', 409)
        reviewer = get_user_model().objects.filter(
            username=username.strip(), is_active=True, groups__name='second_brain_clinicians',
        ).exclude(id=request.user.id).first()
        if not reviewer:
            return error('Choose another active clinician in this workspace.')
        # Reassignment revokes the previous reviewer’s case access.
        case.review_tasks.filter(status='pending').update(status='cancelled')
        task = ReviewTask.objects.create(case=case, reviewer=reviewer, case_revision=case.revision)
        audit(request, case, 'case_review_assigned', task_id=task.id)
        return JsonResponse(task_summary(task), status=201)


@api(['GET', 'PATCH'])
def review_item(request, task_id):
    with transaction.atomic():
        tasks = ReviewTask.objects.filter(reviewer=request.user, case__is_synthetic=True)
        reference = get_object_or_404(tasks.only('case_id'), id=task_id)
        case = get_object_or_404(Case.objects.select_for_update(), id=reference.case_id)
        task = get_object_or_404(tasks.select_for_update(), id=task_id, case=case)
        if task.status != 'pending' or task.case_revision != case.revision:
            return error('This review is closed or outdated. Ask the case owner to reassign it.', 409)
        if request.method == 'PATCH':
            status = body(request).get('status')
            if status not in ('reviewed', 'changes_requested'):
                return error('Choose Reviewed or Changes requested.')
            task.status = status
            task.save(update_fields=['status', 'updated_at'])
            audit(request, case, 'case_review_completed', task_id=task.id, status=status)
            return JsonResponse(task_summary(task))
        facts = unseal(case.payload).get('facts', {})
        return JsonResponse({
            **task_summary(task),
            'facts': {FIELDS[key]: value for key, value in facts.items() if key in FIELDS},
            'sources': [{'title': s['title'], 'text': s['text'], 'date': s['date']}
                        for s in map(source_json, case.sources.filter(status='accepted'))],
        })


@api(['GET', 'POST'])
def templates(request):
    owned = DocumentTemplate.objects.filter(owner=request.user)
    if request.method == 'GET':
        return JsonResponse({'templates': list(owned.order_by('title').values('id', 'title', 'fields'))})
    data = body(request)
    title, fields = data.get('title'), data.get('fields')
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 80 or redact(title)[1]:
        return error('Use a short template name without identifiers.')
    if not isinstance(fields, list) or not fields or any(not isinstance(f, str) or f not in FIELDS for f in fields):
        return error('Select supported case fields.')
    template, created = owned.get_or_create(owner=request.user, title=title.strip(), defaults={'fields': list(dict.fromkeys(fields))})
    if not created:
        return error('A template with that name already exists.', 409)
    return JsonResponse({'id': template.id, 'title': template.title, 'fields': template.fields}, status=201)


@api(['GET'])
def evidence_lab(request):
    # A fixed server-owned artifact. No case ID, source, upload or user text enters inference.
    return JsonResponse(json.loads((settings.BASE_DIR / 'fixtures' / 'evidence-review-results.json').read_text()))
