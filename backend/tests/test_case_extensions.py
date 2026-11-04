import json

from django.contrib.auth.models import User, Group
from django.test import Client

from second_brain.models import seal, unseal
from test_workflow import env, post, patch, url, pytestmark, accept_all


def test_private_template_and_approved_snapshot_survives_edit(env):
    client, case, _ = env
    template = post(client, '/api/second_brain/templates/', {
        'title': 'Short referral', 'fields': ['diagnosis'],
    }).json()
    draft = post(client, url(case, 'generate/'), {'revision': 1, 'template_id': template['id']}).json()['drafts'][0]
    assert draft['template_title'] == 'Short referral'
    assert draft['required_fields'] == ['diagnosis']
    draft = accept_all(client, case, draft)
    path = url(case, f"drafts/{draft['id']}/")
    assert post(client, path + 'approve/', {'attest': True, 'revision': draft['revision']}).status_code == 200
    assert b'Short referral' in client.get(path + 'export/').content
    assert patch(client, path, {'revision': draft['revision'], 'paragraph_id': 'p1', 'text': 'Updated wording'}).status_code == 200
    data = unseal(case.payload)
    data['facts']['imaging'] = 'A new synthetic report is available.'
    case.payload = seal(data)
    case.revision += 1
    case.save()
    changes = client.get(url(case, 'workflow/')).json()['changes']
    assert changes['fields'] == ['Imaging']
    assert changes['stale_drafts'] == 1


def clinician(name):
    user = User.objects.create_user(name)
    user.groups.add(Group.objects.get(name='second_brain_clinicians'))
    client = Client()
    client.force_login(user)
    return client


def test_handoff_is_scoped_to_reviewer_and_revision(env):
    client, case, _ = env
    reviewer = clinician('reviewer')
    other = clinician('other')
    task = post(client, url(case, 'assign-review/'), {'reviewer': 'reviewer', 'revision': 1}).json()
    path = f"/api/second_brain/reviews/{task['id']}/"
    assert other.get(path).status_code == 404
    assert reviewer.get(url(case)).status_code == 404
    assert reviewer.get(path).status_code == 200
    case.revision = 2
    case.save()
    assert reviewer.get(path).status_code == 409
    task = post(client, url(case, 'assign-review/'), {'reviewer': 'reviewer', 'revision': 2}).json()
    path = f"/api/second_brain/reviews/{task['id']}/"
    assert patch(reviewer, path, {'status': 'reviewed'}).json()['status'] == 'reviewed'
    assert reviewer.get(path).status_code == 409


def test_evidence_lab_rejects_post_and_never_reads_case_text(env):
    client, case, _ = env
    case.payload = seal({'facts': {'diagnosis': 'CASE-TEXT-MUST-NOT-ENTER-AI'}})
    case.save()
    endpoint = '/api/second_brain/evidence-lab/'
    response = client.get(endpoint, {'text': 'UNTRUSTED-QUERY'})
    assert response.status_code == 200
    assert b'CASE-TEXT-MUST-NOT-ENTER-AI' not in response.content
    assert b'UNTRUSTED-QUERY' not in response.content
    assert response.json()['mode'] == 'offline_fixture_inference'
    assert post(client, endpoint, {'text': 'UNTRUSTED-BODY'}).status_code == 405
