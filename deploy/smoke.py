"""Container-only smoke check using synthetic fixtures and an isolated volume."""
import os
import sys
from pathlib import Path
sys.path.insert(0, '/app/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from second_brain.intake import extract
from second_brain.models import Case
call_command('migrate', interactive=False, verbosity=0)
call_command('seed_demo', verbosity=0)
credentials = dict(line.split(': ', 1) for line in (settings.RUNTIME / 'demo-login.txt').read_text().splitlines())
client = Client()
assert client.login(username=credentials['Username'], password=credentials['Password'])
assert client.get('/', secure=True).status_code == 200
assert Case.objects.count() == 1
for name in ('synthetic-note.png', 'synthetic-scan.pdf'):
    path = settings.BASE_DIR / 'fixtures' / name
    text, counts, method, low = extract(SimpleUploadedFile(name, path.read_bytes()))
    assert len(text.strip()) > 50, name
    print(f'{name}: extracted and screened ({method})')
print('PASS: login, frontend, persistent case and Linux image/scanned-PDF OCR')
