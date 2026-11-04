import json,secrets,hashlib,mimetypes
from datetime import date,timedelta
from pathlib import Path
from functools import wraps
from django.conf import settings
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.models import User
from django.db import transaction
from django.http import JsonResponse,FileResponse,HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from .models import Case,Source,Draft,DraftRevision,AuditEvent,LoginAttempt,seal,unseal
from .privacy import redact
from . import sarvam
from .quality import flags
from .intake import extract,IntakeError
from .documents import make_draft,digest,TYPES,FIELDS,readability

def error(message,status=422): return JsonResponse({'error':message},status=status)
def body(request):
    try:
        data=json.loads(request.body)
        if not isinstance(data,dict): raise ValueError()
        return data
    except (ValueError,UnicodeDecodeError): raise ValueError('A JSON object is required.')
def api(methods):
    def deco(fn):
        @require_http_methods(methods)
        @wraps(fn)
        def wrapped(request,*args,**kwargs):
            if not request.user.is_authenticated: return error('Sign in to access this workspace.',401)
            if not request.user.groups.filter(name='second_brain_clinicians').exists(): return error('Authorised clinician role required.',403)
            try: return fn(request,*args,**kwargs)
            except (ValueError,IntakeError) as e: return error(str(e))
        return wrapped
    return deco

def audit(request,case,action,**detail): AuditEvent.objects.create(case=case,actor=request.user if request.user.is_authenticated else None,action=action,detail=detail)
def case_for(request,id,lock=False):
    qs=Case.objects.select_for_update() if lock else Case.objects
    return get_object_or_404(qs,id=id,owner=request.user,is_synthetic=True)
def invalidate(case):
    case.revision+=1;case.save(update_fields=['revision'])
    case.drafts.update(status='in_review',approved_hash='',approved_by=None,approved_at=None)
def source_json(s): return {'id':str(s.id),'status':s.status,'created_at':s.created_at.isoformat(),**unseal(s.payload)}
def draft_json(d):
    p=unseal(d.payload)
    return {'id':str(d.id),'type':d.doc_type,'status':d.status,'revision':d.revision,'approved_by':d.approved_by.username if d.approved_by else None,'approved_at':d.approved_at.isoformat() if d.approved_at else None,'readability':readability(p['paragraphs']) if d.doc_type=='patient_handout' else None,**p}
def detail(case):
    data=unseal(case.payload)
    sources=[source_json(s) for s in case.sources.order_by('created_at')]
    return {'id':str(case.id),'alias':case.alias,'is_synthetic':case.is_synthetic,'revision':case.revision,**data,'sources':sources,'quality_flags':flags(data,sources),'drafts':[draft_json(d) for d in case.drafts.order_by('created_at')],'events':[{'id':str(a.id),'actor':a.actor.username if a.actor else 'system','action':a.action,'detail':a.detail,'at':a.at.isoformat()} for a in case.events.select_related('actor').order_by('-at')[:100]]}

@ensure_csrf_cookie
@require_http_methods(['GET','POST','DELETE'])
def session(request):
    if request.method=='DELETE': logout(request);return JsonResponse({'ok':True})
    if request.method=='POST':
        try: data=body(request)
        except ValueError as e: return error(str(e))
        key=hashlib.sha256((request.META.get('REMOTE_ADDR','')+str(data.get('username',''))).encode()).hexdigest()
        attempt,_=LoginAttempt.objects.get_or_create(key=key)
        if attempt.failures>=8 and timezone.now()-attempt.last<timedelta(minutes=15): return error('Too many sign-in attempts. Try again in 15 minutes.',429)
        user=authenticate(request,username=data.get('username'),password=data.get('password'))
        if not user:
            attempt.failures=attempt.failures+1 if timezone.now()-attempt.last<timedelta(minutes=15) else 1;attempt.save();return error('Invalid username or password.',401)
        if not user.groups.filter(name='second_brain_clinicians').exists(): return error('Authorised clinician role required.',403)
        attempt.delete();login(request,user)
    return JsonResponse({'authenticated':request.user.is_authenticated,'username':request.user.username if request.user.is_authenticated else None,'mode':'synthetic-only','care_connected':False,'external_ai':bool(settings.SARVAM_API_KEY),'sarvam_languages':sarvam.LANGUAGES})

@api(['GET','POST'])
def cases(request):
    if request.method=='GET':
        return JsonResponse({'cases':[{'id':str(c.id),'alias':c.alias,'revision':c.revision,'diagnosis':unseal(c.payload)['facts'].get('diagnosis','Not recorded')} for c in Case.objects.filter(owner=request.user,is_synthetic=True)]})
    data=body(request)
    if data.get('is_synthetic') is not True:
        audit(request,None,'synthetic_guard_rejected');return error('Hackathon mode accepts explicitly synthetic cases only.')
    alias=data.get('alias','')
    if not isinstance(alias,str) or not __import__('re').fullmatch(r'SYN-[A-Z0-9-]{1,30}',alias): return error('Use a synthetic alias such as SYN-ONC-002. Do not use a patient name.')
    case=Case.objects.create(owner=request.user,alias=alias,payload=seal({'facts':{},'meeting_date':'','attendees':'','confirmed':False}))
    audit(request,case,'case_created');return JsonResponse(detail(case),status=201)

@api(['GET','PATCH'])
def case_detail(request,id):
    with transaction.atomic():
        case=case_for(request,id,True)
        if request.method=='GET':
            audit(request,case,'history_viewed');return JsonResponse(detail(case))
        data=body(request)
        if data.get('revision')!=case.revision: return error('History changed. Reload before saving.',409)
        facts=data.get('facts')
        if not isinstance(facts,dict) or set(facts)-set(FIELDS): return error('Use the supported case fact fields.')
        clean={}
        for k,v in facts.items():
            if not isinstance(v,str) or len(v)>5000: return error('Each fact must be text under 5,000 characters.')
            text,counts=redact(v)
            if counts: return error('Possible direct identifier detected in case facts. Remove it before saving.')
            clean[k]=text.strip()
        if data.get('confirmed') is not True: return error('Clinician confirmation of the supplied facts is required.')
        for field in ['meeting_date','attendees']:
            value=data.get(field,'')
            if not isinstance(value,str) or len(value)>1000 or redact(value)[1]: return error('Invalid meeting metadata or possible patient identifier.')
        case.payload=seal({'facts':clean,'meeting_date':data.get('meeting_date',''),'attendees':data.get('attendees',''),'confirmed':True})
        case.save(update_fields=['payload']);invalidate(case);audit(request,case,'facts_confirmed',revision=case.revision)
        return JsonResponse(detail(case))

@api(['POST'])
def intake(request,id):
    case=case_for(request,id)
    data=body(request) if request.content_type=='application/json' else request.POST
    title=data.get('title','Imported note');category=data.get('category','Clinical note');event_date=data.get('date','')
    if not isinstance(title,str) or not 1<=len(title)<=120 or redact(title)[1]: return error('Use a short identifier-free source title.')
    if category not in ['Clinical note','Pathology','Imaging report','Medication list','Treatment record','Follow-up','Dictation transcript']: return error('Unsupported history category.')
    try: date.fromisoformat(event_date)
    except (ValueError,TypeError): return error('A valid source date is required; do not infer a date.')
    original_input=None
    if request.content_type=='application/json':
        data=body(request)
        if data.get('is_synthetic') is not True: return error('Confirm that this source is synthetic.')
        text=data.get('text','')
        if not isinstance(text,str) or not text.strip() or len(text)>100000: return error('Add source text (maximum 100,000 characters).')
        text,counts=redact(text);method='Typed / pasted note';low=0
        if data.get('translate') is True:
            if data.get('external_consent') is not True: return error('Confirm sending synthetic text to Sarvam.')
            original_input=text
            text=sarvam.translate(text,data.get('source_language'))
            text,extra=redact(text)
            for key,value in extra.items(): counts[key]=counts.get(key,0)+value
            method='Sarvam translation to English'
    else:
        data=request.POST
        if data.get('is_synthetic')!='true': return error('Confirm that this upload is synthetic.')
        if 'file' not in request.FILES: return error('Select a supported file.')
        if data.get('sarvam_audio')=='true':
            if data.get('external_consent')!='true': return error('Confirm sending synthetic audio to Sarvam.')
            text=sarvam.transcribe(request.FILES['file'],data.get('audio_mode','transcribe'))
            text,counts=redact(text);method='Sarvam audio '+data.get('audio_mode','transcribe');low=0
        else:
            text,counts,method,low=extract(request.FILES['file'])
    source=Source.objects.create(case=case,payload=seal({'title':title,'category':category,'date':event_date,'text':text,'original':text,'original_input':original_input,'method':method,'redactions':counts,'low_confidence_lines':low,'privacy_reviewed':False}))
    audit(request,case,'source_ingested',source_id=str(source.id),method=method,redaction_count=sum(counts.values()))
    return JsonResponse(source_json(source),status=201)

@api(['PATCH'])
def review_source(request,id,source_id):
    with transaction.atomic():
        case=case_for(request,id,True);source=get_object_or_404(Source.objects.select_for_update(),id=source_id,case=case)
        data=body(request);p=unseal(source.payload)
        if source.status!='pending': return error('Reviewed sources are immutable. Add a new source for a correction.',409)
        if data.get('status') not in ['accepted','rejected']: return error('Accept or reject this source.')
        if data['status']=='accepted':
            text=data.get('text',p['text'])
            if not isinstance(text,str) or not text.strip() or len(text)>100000: return error('Corrected source text is required.')
            text,counts=redact(text)
            if counts: return error('Possible identifiers remain. Remove them and review again.')
            if data.get('privacy_reviewed') is not True: return error('Confirm privacy and transcription review before accepting.')
            p['text']=text;p['privacy_reviewed']=True
        source.payload=seal(p);source.status=data['status'];source.save();invalidate(case)
        audit(request,case,'source_'+source.status,source_id=str(source.id),revision=case.revision)
        return JsonResponse(detail(case))

@api(['POST'])
def generate(request,id):
    with transaction.atomic():
        case=case_for(request,id,True);data=body(request);p=unseal(case.payload)
        if data.get('revision')!=case.revision: return error('Case changed. Reload before drafting.',409)
        if not case.is_synthetic or not p.get('confirmed'): return error('Confirm synthetic case facts before drafting.')
        if case.sources.filter(status='pending').exists(): return error('Review or reject all pending sources before drafting.',409)
        if not p.get('facts',{}).get('diagnosis') or not p.get('facts',{}).get('mdt_plan'): return error('Provide the clinician-recorded diagnosis and MDT plan. The system cannot infer them.')
        template = None
        if 'template_id' in data:
            from .models import DocumentTemplate
            if type(data['template_id']) is not int:
                return error('Choose a saved template.')
            template = get_object_or_404(DocumentTemplate, id=data['template_id'], owner=request.user)
        types = ['custom'] if template else data.get('document_types', list(TYPES))
        if not isinstance(types,list) or not types or any(not isinstance(t,str) or (t not in TYPES and not template) for t in types) or len(set(types))!=len(types): return error('Unsupported or duplicate document type.')
        sources=[source_json(s) for s in case.sources.filter(status='accepted')];p['revision']=case.revision
        for kind in types:
            payload=make_draft(case.id,p,kind,sources,template)
            d=Draft.objects.create(case=case,doc_type=kind,payload=seal(payload))
            audit(request,case,'draft_generated',draft_id=str(d.id),engine='template',case_revision=case.revision)
        return JsonResponse(detail(case),status=201)

@api(['PATCH','POST'])
def edit_draft(request,id,draft_id):
    with transaction.atomic():
        case=case_for(request,id,True);d=get_object_or_404(Draft.objects.select_for_update(),case=case,id=draft_id);data=body(request);p=unseal(d.payload)
        if data.get('revision')!=d.revision: return error('Draft changed. Reload before editing.',409)
        paragraph=next((x for x in p['paragraphs'] if x['id']==data.get('paragraph_id')),None)
        if paragraph is None: return error('Paragraph not found.',404)
        DraftRevision.objects.get_or_create(draft=d,revision=d.revision,defaults={'payload':d.payload,'actor':request.user})
        if 'text' in data:
            value=data['text']
            if not isinstance(value,str) or not value.strip() or len(value)>10000: return error('Paragraph must contain text under 10,000 characters.')
            text,counts=redact(value)
            if counts: return error('Possible direct identifiers detected. Remove them before saving.')
            paragraph['text']=text;paragraph['review_status']='pending';paragraph['citation_status']='unverified'
        else:
            if data.get('review_status') not in ['accepted','rejected','pending']: return error('Invalid paragraph review status.')
            paragraph['review_status']=data['review_status']
        d.payload=seal(p);d.revision+=1;d.status='in_review';d.approved_hash='';d.approved_by=None;d.approved_at=None;d.save()
        audit(request,case,'paragraph_edited' if 'text' in data else 'paragraph_reviewed',draft_id=str(d.id),paragraph_id=paragraph['id'],revision=d.revision,review_status=paragraph['review_status'])
        return JsonResponse(draft_json(d))

@api(['POST'])
def approve(request,id,draft_id):
    with transaction.atomic():
        case=case_for(request,id,True);d=get_object_or_404(Draft.objects.select_for_update(),case=case,id=draft_id);data=body(request);p=unseal(d.payload)
        if data.get('revision')!=d.revision: return error('Draft changed. Reload before approval.',409)
        if p['case_revision']!=case.revision: return error('History changed after this draft was created. Generate a new draft.',409)
        if case.sources.filter(status='pending').exists(): return error('Review pending history sources first.',409)
        if data.get('attest') is not True: return error('Clinical accuracy and privacy attestation required.')
        if any(x['review_status']=='pending' for x in p['paragraphs']): return error('Review every paragraph before approval.',409)
        for field in p.get('required_fields', []):
            paragraph = next((x for x in p['paragraphs'] if x['title'] == FIELDS[field]), None)
            if not paragraph or paragraph['review_status'] != 'accepted':
                return error('Review and accept every required template section.', 409)
        included=[x for x in p['paragraphs'] if x['review_status']=='accepted']
        if not included: return error('Cannot approve an empty document.',409)
        if any('[MISSING:' in x['text'] for x in included): return error('Resolve or reject paragraphs with missing facts before approval.',409)
        if any(any(s not in p['references'] for s in x['source_ids']) for x in included): return error('Unresolved source reference.',409)
        d.status='approved';d.approved_hash=digest(p);d.approved_by=request.user;d.approved_at=timezone.now();d.save()
        audit(request,case,'draft_approved',draft_id=str(d.id),revision=d.revision,hash=d.approved_hash)
        return JsonResponse(draft_json(d))

@api(['GET'])
def export(request,id,draft_id):
    with transaction.atomic():
        case=case_for(request,id,True);d=get_object_or_404(Draft,case=case,id=draft_id);p=unseal(d.payload)
        if d.status!='approved' or not secrets.compare_digest(d.approved_hash,digest(p)) or p['case_revision']!=case.revision or case.sources.filter(status='pending').exists(): return error('Export blocked: the current document and history must have matching clinician approval.',409)
        text=f"SYNTHETIC CASE — HACKATHON PROTOTYPE\n{p.get('template_title') or TYPES.get(d.doc_type, 'Custom document')}\nCase: {case.alias}\nApproved by: {d.approved_by.username} | {d.approved_at.isoformat()}\nRevision: {d.revision} | SHA-256: {d.approved_hash}\n\n"
        for para in p['paragraphs']:
            if para['review_status']=='accepted': text+=para['title']+'\n'+para['text']+'\nSources: '+(', '.join(para['source_ids']) or 'Administrative text')+'\n\n'
        text+='SOURCE REGISTER\n'
        for key,value in p['references'].items(): text+=f"{key} | {value['title']}\n{value['text']}\n\n"
        text+='Administrative record of clinician-supplied facts. No independent diagnosis, staging, or treatment recommendation.\n'
        audit(request,case,'draft_exported',draft_id=str(d.id),hash=d.approved_hash)
        response=HttpResponse(text,content_type='text/plain; charset=utf-8');response['Content-Disposition']=f'attachment; filename="{case.alias}-{d.doc_type}-v{d.revision}.txt"';return response

def frontend(request,path=''):
    root=(settings.BASE_DIR/'frontend'/'dist').resolve()
    target=(root/(path or 'index.html')).resolve()
    if not target.is_relative_to(root): return HttpResponse(status=404)
    if not target.is_file():
        if Path(path).suffix: return HttpResponse(status=404)
        target=root/'index.html'
    if not target.exists(): return HttpResponse('Build frontend first: cd frontend && npm run build',status=503)
    return FileResponse(target.open('rb'),content_type=mimetypes.guess_type(str(target))[0] or 'application/octet-stream')


@api(['POST'])
def query_history(request,id):
    from .queries import answer
    with transaction.atomic():
        case=case_for(request,id,True);data=body(request)
        question=data.get('question')
        if not isinstance(question,str) or not 3<=len(question.strip())<=1000:
            return error('Enter a question between 3 and 1,000 characters.')
        if data.get('revision')!=case.revision:
            return error('Patient history changed. Reload the case before asking again.',409)
        result=answer(question.strip(),case.id,case.revision,unseal(case.payload),[source_json(s) for s in case.sources.all()])
        audit(request,case,'history_queried',case_revision=case.revision,status=result['status'],result_count=len(result['items']),source_ids=list(dict.fromkeys(i['source_id'] for i in result['items'])))
        return JsonResponse(result)
