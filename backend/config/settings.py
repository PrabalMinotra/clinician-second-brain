import os
from pathlib import Path
from cryptography.fernet import Fernet
BASE_DIR = Path(__file__).resolve().parents[2]
RUNTIME = Path(os.environ.get('SECOND_BRAIN_RUNTIME', str(BASE_DIR / '.runtime')))
RUNTIME.mkdir(mode=0o700, exist_ok=True)
def local_secret(name, generate):
    path = RUNTIME / name
    if not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f: f.write(generate())
    return path.read_text().strip()
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY') or local_secret('django-key', lambda: __import__('secrets').token_urlsafe(48))
SECOND_BRAIN_KEY = os.environ.get('SECOND_BRAIN_KEY') or local_secret('data-key', lambda: Fernet.generate_key().decode())
DEBUG = False
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']
INSTALLED_APPS = ['django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','second_brain']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','second_brain.middleware.PrivateResponses']
ROOT_URLCONF = 'config.urls'
DATABASES = {'default': {'ENGINE':'django.db.backends.sqlite3','NAME': RUNTIME / 'second-brain.sqlite3','OPTIONS':{'timeout':20}}}
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
USE_TZ=True
TIME_ZONE='Asia/Kolkata'
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE='Strict'
CSRF_COOKIE_SAMESITE='Strict'
SESSION_COOKIE_AGE=3600
SESSION_EXPIRE_AT_BROWSER_CLOSE=True
CSRF_TRUSTED_ORIGINS=['http://127.0.0.1:5173','http://localhost:5173','http://127.0.0.1:8000']
DATA_UPLOAD_MAX_MEMORY_SIZE=12*1024*1024
FILE_UPLOAD_MAX_MEMORY_SIZE=12*1024*1024
SECURE_CONTENT_TYPE_NOSNIFF=True
X_FRAME_OPTIONS='DENY'
LOGGING={'version':1,'disable_existing_loggers':False,'handlers':{'null':{'class':'logging.NullHandler'}},'loggers':{'django.request':{'handlers':['null'],'propagate':False}}}

# Server-only credential; the private runtime file is ignored by source control.
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY") or ((RUNTIME / "sarvam-key").read_text().strip() if (RUNTIME / "sarvam-key").exists() else "")

# Hosted synthetic demo: trust forwarded HTTPS only behind the hosting proxy.
HOSTED_DEMO = os.environ.get("HOSTED_DEMO") == "1"
if HOSTED_DEMO:
    if not os.environ.get("DJANGO_SECRET_KEY") or not os.environ.get("SECOND_BRAIN_KEY"):
        raise RuntimeError("Hosted demo requires stable DJANGO_SECRET_KEY and SECOND_BRAIN_KEY")
    ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise RuntimeError("Set explicit DJANGO_ALLOWED_HOSTS for the hosted demo")
    CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS]
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600
