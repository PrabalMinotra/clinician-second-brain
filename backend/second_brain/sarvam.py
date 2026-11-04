"""Server-only Sarvam adapter. Never log provider bodies or credentials."""
import httpx
from django.conf import settings

LANGUAGES = dict(zip(
    ['en','hi','bn','gu','kn','ml','mr','od','pa','ta','te','as','brx','doi','kok','ks','mai','mni','ne','sa','sat','sd','ur'],
    ['English','Hindi','Bengali','Gujarati','Kannada','Malayalam','Marathi','Odia','Punjabi','Tamil','Telugu','Assamese','Bodo','Dogri','Konkani','Kashmiri','Maithili','Manipuri','Nepali','Sanskrit','Santali','Sindhi','Urdu']))
LANGUAGES = {k+'-IN': v for k,v in LANGUAGES.items()}
AUDIO_TYPES = {'.wav':'audio/wav','.mp3':'audio/mpeg','.m4a':'audio/mp4','.ogg':'audio/ogg','.flac':'audio/flac','.webm':'audio/webm'}

def call(endpoint, **kwargs):
    if not settings.SARVAM_API_KEY:
        raise ValueError('Sarvam is not configured. Set SARVAM_API_KEY on the server.')
    try:
        response = httpx.post('https://api.sarvam.ai/'+endpoint,
            headers={'api-subscription-key': settings.SARVAM_API_KEY},
            timeout=httpx.Timeout(60, connect=10), follow_redirects=False, **kwargs)
        if response.status_code != 200:
            messages = {401:'Sarvam credentials were rejected.',403:'Sarvam access was denied.',
                402:'Sarvam credits are exhausted.',429:'Sarvam rate limit reached. Try again later.'}
            raise ValueError(messages.get(response.status_code, 'Sarvam could not process this input. Check the file or try again later.'))
        result = response.json()
        if not isinstance(result, dict): raise ValueError('Sarvam returned an invalid response.')
        return result
    except httpx.RequestError:
        raise ValueError('Sarvam is unavailable or timed out. Try again later.') from None
    except (TypeError, __import__('json').JSONDecodeError):
        raise ValueError('Sarvam returned an invalid response.') from None

def result_text(result, key):
    text = result.get(key)
    if not isinstance(text,str) or not text.strip() or len(text)>100000:
        raise ValueError('Sarvam returned no usable text. Try another input.')
    return text

def translate(text, language):
    if language not in LANGUAGES: raise ValueError('Select a supported source language.')
    if len(text)>2000: raise ValueError('Translation limit: 2,000 characters. Split longer notes into separate sources.')
    return result_text(call('translate', json={'input':text, 'source_language_code':language,
        'target_language_code':'en-IN','model':'sarvam-translate:v1'}),'translated_text')

def transcribe(upload, mode):
    from pathlib import Path
    suffix=Path(upload.name).suffix.lower()
    if suffix not in AUDIO_TYPES: raise ValueError('Use WAV, MP3, M4A, OGG, FLAC or WebM audio (under 30 seconds).')
    if mode not in ['transcribe','translate']: raise ValueError('Unsupported transcription mode.')
    data=upload.read(10*1024*1024+1)
    if not data or len(data)>10*1024*1024: raise ValueError('Audio must be nonempty and under 10 MB.')
    return result_text(call('speech-to-text', files={'file':('dictation'+suffix,data,AUDIO_TYPES[suffix])},
        data={'model':'saaras:v4','mode':mode,'language_code':'unknown'}),'transcript')
