from unittest.mock import patch
import httpx
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from second_brain import sarvam
from second_brain.models import Source
from test_workflow import env, url, post
pytestmark=pytest.mark.django_db

def fields(**extra):
    return {'is_synthetic':True,'title':'Synthetic dictation','category':'Dictation transcript','date':'2026-10-31',**extra}

@override_settings(SARVAM_API_KEY='unit-test-secret')
def test_translation_contract_and_review(env):
    client,case,_=env
    with patch.object(sarvam.httpx,'post',return_value=httpx.Response(200,json={'translated_text':'Synthetic follow-up on Monday.'})) as call:
        r=post(client,url(case,'intake/'),fields(text='काल्पनिक रिकॉर्ड',translate=True,source_language='hi-IN',external_consent=True))
    assert r.status_code==201
    assert r.json()['status']=='pending' and not r.json()['privacy_reviewed']
    assert r.json()['original_input']=='काल्पनिक रिकॉर्ड'
    assert call.call_args.kwargs['json']['model']=='sarvam-translate:v1'
    assert call.call_args.kwargs['headers']['api-subscription-key']=='unit-test-secret'
    assert 'Synthetic follow-up' not in Source.objects.get().payload

@pytest.mark.parametrize('extra',[{'external_consent':False},{'is_synthetic':False},{'date':'bad'},{'source_language':'invalid'},{'text':'x'*2001}])
def test_translation_rejected_without_provider_call(env,extra):
    client,case,_=env
    data=fields(text='Synthetic note',translate=True,source_language='hi-IN',external_consent=True);data.update(extra)
    with patch.object(sarvam.httpx,'post') as call:
        assert post(client,url(case,'intake/'),data).status_code==422
        call.assert_not_called()
    assert not Source.objects.exists()

@override_settings(SARVAM_API_KEY='unit-test-secret')
def test_audio_contract_and_screening(env):
    client,case,_=env
    data={k:('true' if v is True else v) for k,v in fields().items()}
    data.update(file=SimpleUploadedFile('private-name.wav',b'RIFFsynthetic'),sarvam_audio='true',external_consent='true',audio_mode='translate')
    with patch.object(sarvam.httpx,'post',return_value=httpx.Response(200,json={'transcript':'Patient name: Fictional Person\nSynthetic follow-up.'})) as call:
        r=client.post(url(case,'intake/'),data)
    assert r.status_code==201
    assert r.json()['status']=='pending' and 'Fictional Person' not in r.json()['text']
    assert call.call_args.kwargs['files']['file'][0]=='dictation.wav'
    assert call.call_args.kwargs['data']['mode']=='translate'

@pytest.mark.parametrize('response',[httpx.Response(403,text='secret-provider-body'),httpx.Response(200,json={}),httpx.Response(200,text='bad json'),httpx.Response(200,json=[])])
@override_settings(SARVAM_API_KEY='unit-test-secret')
def test_provider_failures_are_sanitized(env,response):
    client,case,_=env
    with patch.object(sarvam.httpx,'post',return_value=response):
        r=post(client,url(case,'intake/'),fields(text='Synthetic',translate=True,source_language='hi-IN',external_consent=True))
    assert r.status_code==422 and 'secret-provider-body' not in r.content.decode()
    assert not Source.objects.exists()

@override_settings(SARVAM_API_KEY='')
def test_missing_key():
    with patch.object(sarvam.httpx,'post') as call, pytest.raises(ValueError,match='not configured'):
        sarvam.translate('Synthetic','en-IN')
    call.assert_not_called()

@pytest.mark.parametrize('consent',['false',''])
def test_audio_needs_external_consent(env,consent):
    client,case,_=env
    with patch.object(sarvam.httpx,'post') as call:
        r=client.post(url(case,'intake/'),{**fields(), 'is_synthetic':'true','sarvam_audio':'true','external_consent':consent,'file':SimpleUploadedFile('test.wav',b'RIFF')})
    assert r.status_code==422
    call.assert_not_called()

@override_settings(SARVAM_API_KEY='unit-test-secret')
def test_timeout_is_sanitized(env):
    client,case,_=env
    with patch.object(sarvam.httpx,'post',side_effect=httpx.ConnectTimeout('secret detail')):
        r=post(client,url(case,'intake/'),fields(text='Synthetic',translate=True,source_language='hi-IN',external_consent=True))
    assert r.status_code==422 and 'secret detail' not in r.content.decode()
