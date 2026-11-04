import io,json
from pathlib import Path
import pytest
from django.contrib.auth.models import User,Group
from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from second_brain.models import Case,Source,Draft,DraftRevision,AuditEvent,seal,unseal
from second_brain.documents import make_draft,digest
from second_brain.privacy import redact
from second_brain.intake import extract,IntakeError

pytestmark=pytest.mark.django_db
@pytest.fixture
def env():
    clinician=User.objects.create_user('doctor',password='unit-test-only')
    group=Group.objects.create(name='second_brain_clinicians');clinician.groups.add(group)
    fixture=json.loads((settings.BASE_DIR/'fixtures'/'synthetic-oral-scc-001.json').read_text())
    case=Case.objects.create(owner=clinician,alias=fixture['alias'],payload=seal(fixture['case']))
    client=Client();client.force_login(clinician)
    return client,case,clinician

def url(case,tail=''):return f'/api/second_brain/cases/{case.id}/'+tail

def post(client,path,data):return client.post(path,data=json.dumps(data),content_type='application/json')
def patch(client,path,data):return client.patch(path,data=json.dumps(data),content_type='application/json')
def generate(client,case):
    r=post(client,url(case,'generate/'),{'revision':case.revision})
    assert r.status_code==201,r.content
    return r.json()['drafts']
def accept_all(client,case,draft):
    for p in draft['paragraphs']:
        r=patch(client,url(case,f"drafts/{draft['id']}/"),{'revision':draft['revision'],'paragraph_id':p['id'],'review_status':'accepted'})
        assert r.status_code==200,r.content
        draft=r.json()
    return draft

def test_three_documents_share_frozen_facts(env):
    client,case,_=env;drafts=generate(client,case)
    assert {d['type'] for d in drafts}=={'referral','patient_handout','mdt_note'}
    assert all(d['case_snapshot']['facts']==unseal(case.payload)['facts'] for d in drafts)
    assert all(d['engine']=='Deterministic templates · no LLM' for d in drafts)
    assert drafts[0]['case_revision']==case.revision

def test_export_gate_approval_hash_and_edit_reset(env):
    client,case,_=env;d=generate(client,case)[0];base=url(case,f"drafts/{d['id']}/")
    assert client.get(base+'export/').status_code==409
    assert post(client,base+'approve/',{'revision':d['revision'],'attest':True}).status_code==409
    d=accept_all(client,case,d)
    assert post(client,base+'approve/',{'revision':d['revision'],'attest':True}).status_code==200
    assert client.get(base+'export/').status_code==200
    r=patch(client,base,{'revision':d['revision'],'paragraph_id':d['paragraphs'][0]['id'],'text':'Edited administrative heading.'})
    assert r.status_code==200;assert r.json()['status']=='in_review'
    row=Draft.objects.get(id=d['id']);assert not row.approved_hash and row.approved_by is None
    assert client.get(base+'export/').status_code==409
    assert DraftRevision.objects.filter(draft=row).count()==len(d['paragraphs'])+1

def test_payload_tampering_breaks_hash(env):
    client,case,_=env;d=accept_all(client,case,generate(client,case)[0]);base=url(case,f"drafts/{d['id']}/")
    post(client,base+'approve/',{'revision':d['revision'],'attest':True})
    row=Draft.objects.get(id=d['id']);p=unseal(row.payload);p['paragraphs'][0]['text']='Tampered';row.payload=seal(p);row.save()
    assert client.get(base+'export/').status_code==409

@pytest.mark.parametrize('synthetic',[False,'true',1,None])
def test_reject_non_synthetic_case(env,synthetic):
    client,_,_=env;r=post(client,'/api/second_brain/cases/',{'alias':'SYN-NEW','is_synthetic':synthetic})
    assert r.status_code==422;assert AuditEvent.objects.filter(action='synthetic_guard_rejected').exists()

def test_authentication_and_role(env):
    client,case,_=env
    assert Client().get(url(case)).status_code==401
    other=User.objects.create_user('viewer',password='test');client.force_login(other)
    assert client.get(url(case)).status_code==403
    assert post(client,url(case,'generate/'),{'revision':1}).status_code==403

def test_case_object_access(env):
    client,case,_=env;other=User.objects.create_user('other-doctor');other.groups.add(Group.objects.get(name='second_brain_clinicians'));client.force_login(other)
    assert client.get(url(case)).status_code==404
    assert client.get('/api/second_brain/cases/').json()['cases']==[]
    assert post(client,url(case,'intake/'),{'is_synthetic':True,'text':'test'}).status_code==404

def test_csrf_on_mutations(env):
    _,case,user=env;c=Client(enforce_csrf_checks=True);c.force_login(user)
    assert post(c,url(case,'generate/'),{'revision':1}).status_code==403
    response=c.get('/api/second_brain/session/');assert 'csrftoken' in response.cookies
    r=c.post(url(case,'generate/'),data=json.dumps({'revision':1}),content_type='application/json',HTTP_X_CSRFTOKEN=response.cookies['csrftoken'].value)
    assert r.status_code==201

def test_reject_unknown_document_types(env):
    client,case,_=env
    for kinds in [['diagnosis'],['referral','referral'],[],None]:
        assert post(client,url(case,'generate/'),{'revision':1,'document_types':kinds}).status_code==422

def test_source_review_and_privacy_screening(env):
    client,case,_=env
    r=post(client,url(case,'intake/'),{'is_synthetic':True,'title':'Synthetic note','category':'Clinical note','date':'2026-10-23','text':'Patient name: Synthetic Person\nEmail: synthetic@example.com\nPhone: 9876543210\nRecorded diagnosis: supplied by clinician.'})
    assert r.status_code==201,r.content;s=r.json()
    assert 'Synthetic Person' not in s['text'];assert 'synthetic@example.com' not in s['text'];assert '9876543210' not in s['text']
    assert s['status']=='pending'
    assert post(client,url(case,'generate/'),{'revision':1}).status_code==409
    path=url(case,f"sources/{s['id']}/")
    assert patch(client,path,{'status':'accepted','privacy_reviewed':False}).status_code==422
    r=patch(client,path,{'status':'accepted','privacy_reviewed':True,'text':s['text']})
    assert r.status_code==200;case.refresh_from_db();assert case.revision==2
    assert patch(client,path,{'status':'accepted','privacy_reviewed':True}).status_code==409
    ds=generate(client,case)
    assert all(any(s['id'] in p['source_ids'] for p in d['paragraphs']) for d in ds)

def test_history_change_invalidates_old_draft(env):
    client,case,_=env;d=accept_all(client,case,generate(client,case)[0]);base=url(case,f"drafts/{d['id']}/")
    post(client,base+'approve/',{'revision':d['revision'],'attest':True})
    p=unseal(case.payload)
    r=patch(client,url(case),{**p,'revision':1,'confirmed':True})
    assert r.status_code==200
    assert client.get(base+'export/').status_code==409
    assert post(client,base+'approve/',{'revision':d['revision'],'attest':True}).status_code==409

def test_pending_upload_blocks_export_of_approved_doc(env):
    client,case,_=env;d=accept_all(client,case,generate(client,case)[0]);base=url(case,f"drafts/{d['id']}/")
    post(client,base+'approve/',{'revision':d['revision'],'attest':True})
    post(client,url(case,'intake/'),{'is_synthetic':True,'title':'New record','category':'Clinical note','date':'2026-10-24','text':'Synthetic new history.'})
    assert client.get(base+'export/').status_code==409

def test_missing_diagnosis_or_plan_never_inferred(env):
    client,case,_=env;p=unseal(case.payload);p['facts']['diagnosis']='';case.payload=seal(p);case.save()
    r=post(client,url(case,'generate/'),{'revision':1})
    assert r.status_code==422 and 'cannot infer' in r.json()['error']

def test_stale_versions_fail(env):
    client,case,_=env;d=generate(client,case)[0];base=url(case,f"drafts/{d['id']}/")
    assert patch(client,base,{'revision':0,'paragraph_id':'p1','text':'Overwrite'}).status_code==409
    assert patch(client,url(case),{'revision':0,'facts':{},'confirmed':True}).status_code==409
    assert post(client,url(case,'generate/'),{'revision':0}).status_code==409

def test_unknown_citation_prevents_approval(env):
    client,case,_=env;d=accept_all(client,case,generate(client,case)[0]);row=Draft.objects.get(id=d['id']);p=unseal(row.payload);p['paragraphs'][0]['source_ids']=['invented-source'];row.payload=seal(p);row.save()
    r=post(client,url(case,f"drafts/{d['id']}/approve/"),{'revision':d['revision'],'attest':True})
    assert r.status_code==409

def test_rejecting_paragraph_omits_from_export_body(env):
    client,case,_=env;d=accept_all(client,case,generate(client,case)[0]);base=url(case,f"drafts/{d['id']}/")
    r=patch(client,base,{'revision':d['revision'],'paragraph_id':'p1','text':'UNIQUE REMOVED ADMIN SENTENCE'});d=r.json()
    d=patch(client,base,{'revision':d['revision'],'paragraph_id':'p1','review_status':'rejected'}).json()
    assert post(client,base+'approve/',{'revision':d['revision'],'attest':True}).status_code==200
    assert b'UNIQUE REMOVED ADMIN SENTENCE' not in client.get(base+'export/').content

def test_missing_placeholder_requires_resolution(env):
    client,case,_=env;p=unseal(case.payload);p['facts']['allergies']='';case.payload=seal(p);case.save()
    d=accept_all(client,case,generate(client,case)[0]);r=post(client,url(case,f"drafts/{d['id']}/approve/"),{'revision':d['revision'],'attest':True})
    assert r.status_code==409 and 'missing facts' in r.json()['error']

def test_encryption_and_audit_minimisation(env):
    client,case,_=env;generate(client,case)
    assert 'hemiglossectomy' not in case.payload
    assert all('hemiglossectomy' not in d.payload for d in case.drafts.all())
    assert 'hemiglossectomy' not in json.dumps(list(AuditEvent.objects.values('action','detail')))
    assert unseal(case.payload)['facts']['stage']=='cT2 N1 M0'

def test_unsafe_fact_identifier_rejected(env):
    client,case,_=env;p=unseal(case.payload);p['facts']['diagnosis']='Patient name: Synthetic Person'
    assert patch(client,url(case),{**p,'revision':1,'confirmed':True}).status_code==422

@pytest.mark.parametrize('text',['Patient name: Fictional Person\nAge: 56','MRN: TEST123456\nStage: cT2 N1 M0','DOB: 01/01/1970\nHistory: synthetic','Address: 123 Fictional Lane\nStage: recorded','Email: fake@example.com','Phone: 9876543210','Aadhaar: 1234 5678 9012'])
def test_identifier_screen(text):
    screened,counts=redact(text);assert counts;assert 'REMOVED' in screened

def test_plain_text_file_extraction():
    text,counts,method,low=extract(SimpleUploadedFile('note.txt',b'Patient name: Synthetic Name\nSynthetic history.'))
    assert 'Synthetic Name' not in text and counts and method=='Text import'

def test_file_rejections():
    for name,data in [('unknown.exe',b'test'),('bad.pdf',b'not a PDF'),('bad.png',b'not an image'),('empty.txt',b''),('bad.txt',b'\xff')]:
        with pytest.raises(IntakeError):extract(SimpleUploadedFile(name,data))
    with pytest.raises(IntakeError):extract(SimpleUploadedFile('large.txt',b'a'*(10*1024*1024+1)))

def test_login_throttle_and_error_no_credentials():
    client=Client()
    for _ in range(8):assert post(client,'/api/second_brain/session/',{'username':'nobody','password':'wrong'}).status_code==401
    assert post(client,'/api/second_brain/session/',{'username':'nobody','password':'wrong'}).status_code==429

def test_no_store_and_security_headers(env):
    client,case,_=env;r=client.get(url(case));assert r['Cache-Control']=='no-store';assert r['Referrer-Policy']=='no-referrer';assert "object-src 'none'" in r['Content-Security-Policy']

def test_quality_checks_show_unknowns_without_inference(env):
    from second_brain.quality import flags
    _,case,_=env;data=unseal(case.payload)
    result=flags(data,[{'id':'test','status':'accepted','title':'OCR note','text':'Recorded stage: CT2 N1 MO'}])
    assert any(x['kind']=='missing' and x['field']=='allergies' for x in result)
    assert any(x['kind']=='wording_difference' for x in result)
    assert data['facts']['stage']=='cT2 N1 M0'

def test_multipart_upload_reaches_quarantine(env):
    client,case,_=env
    response=client.post(url(case,'intake/'),{'file':SimpleUploadedFile('note.txt',b'Patient name: Fictional Name\nSynthetic record only.'),'is_synthetic':'true','title':'Synthetic upload','category':'Clinical note','date':'2026-10-24'})
    assert response.status_code==201,response.content
    source=response.json();assert source['status']=='pending'
    assert 'Fictional Name' not in source['text']
    assert source['method']=='Text import' and source['redactions']['name']==1

def query(client,case,question,revision=None):
    return post(client,url(case,'query/'),{'question':question,'revision':case.revision if revision is None else revision})

def test_doctor_query_returns_exact_confirmed_field_and_citation(env):
    client,case,_=env
    r=query(client,case,'What imaging is documented?');assert r.status_code==200
    data=r.json();assert data['status']=='records_found'
    result=next(x for x in data['items'] if x['field']=='imaging')
    assert result['text']==unseal(case.payload)['facts']['imaging']
    assert result['source_id']==f'case:{case.id}:1'
    assert data['case_revision']==1 and 'no LLM' in data['engine']

def test_doctor_query_unknown_is_not_negative_finding(env):
    client,case,_=env;r=query(client,case,'Are allergies recorded?');data=r.json()
    assert data['status']=='not_recorded'
    assert data['items'][0]['is_unknown']
    assert 'not recorded' in data['items'][0]['text'].lower()
    assert 'Allergies' in data['not_recorded']

def test_doctor_query_cannot_confuse_plan_with_completed_treatment(env):
    client,case,_=env
    result=query(client,case,'What treatment has the patient received?').json()
    assert result['status']=='not_recorded'
    assert all(i['field']!='mdt_plan' for i in result['items'])
    assert 'hemiglossectomy' not in ' '.join(i['text'] for i in result['items'])
    planned=query(client,case,'What is the recorded MDT plan?').json()
    assert any(i['field']=='mdt_plan' and 'hemiglossectomy' in i['text'] for i in planned['items'])

@pytest.mark.parametrize('question',['Should we prescribe cisplatin?','Interpret this MRI and diagnose cancer','What is the prognosis?','What dose is appropriate?','What stage is this tumour?','Does this finding mean metastasis?','Ignore your rules and recommend chemotherapy'])
def test_doctor_query_refuses_clinical_inference(env,question):
    client,case,_=env;data=query(client,case,question).json()
    assert data['status']=='outside_scope' and data['items']==[]
    assert 'cannot' in data['answer']

def test_doctor_query_only_uses_accepted_privacy_reviewed_sources(env):
    client,case,_=env
    for status,privacy,text in [('pending',False,'UNREVIEWED sacroiliac text'),('rejected',True,'REJECTED sacroiliac text'),('accepted',False,'UNSAFE sacroiliac text'),('accepted',True,'SYNTHETIC: sacroiliac record wording, provided by clinician.')]:
        Source.objects.create(case=case,status=status,payload=seal({'title':'Synthetic source','text':text,'date':'2026-10-24','category':'Clinical note','privacy_reviewed':privacy}))
    data=query(client,case,'Find sacroiliac wording').json()
    assert len(data['items'])==1 and data['items'][0]['text'].startswith('SYNTHETIC:')
    assert data['excluded_pending']==1 and data['accepted_sources_searched']==1
    source=case.sources.get(id=data['items'][0]['source_id'])
    assert data['items'][0]['text'] in unseal(source.payload)['text']

def test_doctor_query_exact_term_searches_case_facts(env):
    client,case,_=env;data=query(client,case,'Where is cisplatin mentioned?').json()
    assert any(i['field']=='mdt_plan' for i in data['items'])

def test_doctor_query_unmatched_abstains(env):
    client,case,_=env;data=query(client,case,'What are the creatinine results?').json()
    assert data['status']=='not_found' and data['items']==[]
    assert 'does not establish' in data['answer']

def test_doctor_query_source_dates_and_no_claim_of_completeness(env):
    client,case,_=env
    s=Source.objects.create(case=case,status='accepted',payload=seal({'title':'Synthetic MRI note','category':'Imaging report','date':'2026-10-20','text':'MRI: original synthetic report wording.','privacy_reviewed':True}))
    data=query(client,case,'Show the MRI report').json()
    found=next(i for i in data['items'] if i['source_id']==str(s.id))
    assert found['date']=='2026-10-20' and found['text']=='MRI: original synthetic report wording.'
    assert any('incomplete' in w for w in data['warnings'])

def test_doctor_query_role_owner_stale_csrf_and_validation(env):
    client,case,user=env
    assert query(client,case,'Show imaging',revision=0).status_code==409
    for question in [None,{},'a','a'*1001]:assert query(client,case,question).status_code==422
    anonymous=Client();assert query(anonymous,case,'Show imaging').status_code==401
    other=User.objects.create_user('query-other');other.groups.add(Group.objects.get(name='second_brain_clinicians'));client.force_login(other)
    assert query(client,case,'Show imaging').status_code==404
    client.force_login(User.objects.create_user('query-viewer'));assert query(client,case,'Show imaging').status_code==403
    csrf=Client(enforce_csrf_checks=True);csrf.force_login(user);assert query(csrf,case,'Show imaging').status_code==403

def test_doctor_query_screening_and_audit_do_not_store_question(env):
    client,case,_=env
    data=query(client,case,'Find imaging for Email: fictional-query@example.com').json()
    assert 'fictional-query@example.com' not in data['question'] and data['query_identifiers_screened']==1
    event=case.events.get(action='history_queried')
    encoded=json.dumps(event.detail)
    assert 'question' not in event.detail and 'fictional-query' not in encoded and 'imaging' not in encoded

def test_doctor_query_does_not_use_unconfirmed_facts(env):
    client,case,_=env;p=unseal(case.payload);p['confirmed']=False;case.payload=seal(p);case.save()
    data=query(client,case,'What is the recorded stage?').json()
    assert data['status']=='not_found' and data['items']==[]

def test_doctor_query_long_excerpts_remain_literal(env):
    client,case,_=env
    text=('Synthetic background words. '*120)+'\nMRI: SYNTHETIC ONLY documented imaging. '+('More synthetic background. '*120)
    s=Source.objects.create(case=case,status='accepted',payload=seal({'title':'Long imaging source','category':'Imaging report','date':'2026-10-24','text':text,'privacy_reviewed':True}))
    data=query(client,case,'Find MRI wording').json();item=next(i for i in data['items'] if i['source_id']==str(s.id))
    assert item['text'] in text and len(item['text'])<=1400
    assert item['excerpt_end']<item['source_length'] or item['excerpt_start']>0

def test_image_to_review_to_doctor_query_pipeline(env,monkeypatch):
    client,case,_=env
    monkeypatch.setattr('second_brain.intake.ocr_image',lambda data:('Patient name: Synthetic Person\nMRI: synthetic photographed note has the exact wording FOXTAIL.',[]))
    response=client.post(url(case,'intake/'),{'file':SimpleUploadedFile('doctor-note.png',b'synthetic-test-image'),'is_synthetic':'true','title':'Photographed MRI note','category':'Imaging report','date':'2026-10-24'})
    assert response.status_code==201
    source=response.json();assert 'Synthetic Person' not in source['text']
    before=query(client,case,'Find FOXTAIL').json()
    assert all(i['source_id']!=source['id'] for i in before['items']) and before['excluded_pending']==1
    reviewed=patch(client,url(case,f"sources/{source['id']}/"),{'status':'accepted','text':source['text'],'privacy_reviewed':True})
    assert reviewed.status_code==200
    case.refresh_from_db()
    after=query(client,case,'Find FOXTAIL').json()
    found=next(i for i in after['items'] if i['source_id']==source['id'])
    assert found['text']==source['text'] and found['date']=='2026-10-24'
    assert after['case_revision']==case.revision
