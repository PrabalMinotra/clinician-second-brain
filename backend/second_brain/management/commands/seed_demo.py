import json,os,secrets
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User,Group
from second_brain.models import Case,Source,AuditEvent,seal
from second_brain.documents import make_draft
class Command(BaseCommand):
    help='Create a local synthetic demonstration account and oral SCC case. Never overwrites existing cases.'
    def handle(self,*args,**options):
        user,created=User.objects.get_or_create(username='clinician')
        if created:
            password = os.environ.get('SECOND_BRAIN_DEMO_PASSWORD') or secrets.token_urlsafe(18)
            user.set_password(password)
            user.save()
            path=settings.RUNTIME/'demo-login.txt'
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as f: f.write('Username: clinician\nPassword: '+password+'\n')
        group, _ = Group.objects.get_or_create(name='second_brain_clinicians')
        user.groups.add(group)
        reviewer_password = os.environ.get('SECOND_BRAIN_REVIEWER_PASSWORD')
        if reviewer_password:
            reviewer, created = User.objects.get_or_create(username='demo-reviewer')
            if created:
                reviewer.set_password(reviewer_password)
                reviewer.save(update_fields=['password'])
                reviewer.groups.add(group)
        if Case.objects.filter(owner=user).exists(): self.stdout.write('Existing demo kept unchanged.');return
        fixture=json.loads((settings.BASE_DIR/'fixtures'/'synthetic-oral-scc-001.json').read_text())
        case=Case.objects.create(owner=user,alias=fixture['alias'],is_synthetic=True,payload=seal(fixture['case']))
        for record in fixture['sources']:
            source=Source.objects.create(case=case,status='accepted',payload=seal({**record,'original':record['text'],'redactions':{},'low_confidence_lines':0,'privacy_reviewed':True,'method':'Synthetic fixture'}))
            AuditEvent.objects.create(case=case,actor=user,action='synthetic_fixture_source_loaded',detail={'source_id':str(source.id)})
        AuditEvent.objects.create(case=case,actor=user,action='synthetic_fixture_loaded',detail={'revision':1})
        self.stdout.write('Synthetic case ready. Credentials: .runtime/demo-login.txt (owner-read/write only).')
