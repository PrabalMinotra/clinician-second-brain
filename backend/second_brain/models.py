import uuid,json
from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models

def seal(value): return Fernet(settings.SECOND_BRAIN_KEY.encode()).encrypt(json.dumps(value).encode()).decode()
def unseal(value): return json.loads(Fernet(settings.SECOND_BRAIN_KEY.encode()).decrypt(value.encode()))
class Case(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    alias=models.CharField(max_length=50)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    is_synthetic=models.BooleanField(default=True)
    payload=models.TextField()
    revision=models.PositiveIntegerField(default=1)
    created_at=models.DateTimeField(auto_now_add=True)
class Source(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    case=models.ForeignKey(Case,on_delete=models.CASCADE,related_name='sources')
    payload=models.TextField()
    status=models.CharField(max_length=24,default='pending')
    created_at=models.DateTimeField(auto_now_add=True)
class Draft(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    case=models.ForeignKey(Case,on_delete=models.CASCADE,related_name='drafts')
    doc_type=models.CharField(max_length=24)
    payload=models.TextField()
    revision=models.PositiveIntegerField(default=1)
    status=models.CharField(max_length=24,default='in_review')
    approved_hash=models.CharField(max_length=64,blank=True)
    approved_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True)
    approved_at=models.DateTimeField(null=True)
    created_at=models.DateTimeField(auto_now_add=True)
class AuditEvent(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    case=models.ForeignKey(Case,on_delete=models.CASCADE,related_name='events',null=True)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True)
    action=models.CharField(max_length=50)
    detail=models.JSONField(default=dict)
    at=models.DateTimeField(auto_now_add=True)
class LoginAttempt(models.Model):
    key=models.CharField(max_length=64,unique=True)
    failures=models.PositiveIntegerField(default=0)
    last=models.DateTimeField(auto_now=True)
class DraftRevision(models.Model):
    draft=models.ForeignKey(Draft,on_delete=models.CASCADE,related_name='versions')
    revision=models.PositiveIntegerField()
    payload=models.TextField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['draft','revision'],name='unique_draft_revision')]


class ReviewTask(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name='review_tasks')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    case_revision = models.PositiveIntegerField()
    status = models.CharField(max_length=20, default='pending')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['case'], condition=models.Q(status='pending'),
                                    name='one_pending_case_review'),
        ]


class DocumentTemplate(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=80)
    fields = models.JSONField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner', 'title'], name='unique_owner_template'),
        ]
