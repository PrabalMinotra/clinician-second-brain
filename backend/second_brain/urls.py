from django.urls import path
from . import views as v
urlpatterns=[path('cases/<uuid:id>/query/',v.query_history),path('session/',v.session),path('cases/',v.cases),path('cases/<uuid:id>/',v.case_detail),path('cases/<uuid:id>/intake/',v.intake),path('cases/<uuid:id>/sources/<uuid:source_id>/',v.review_source),path('cases/<uuid:id>/generate/',v.generate),path('cases/<uuid:id>/drafts/<uuid:draft_id>/',v.edit_draft),path('cases/<uuid:id>/drafts/<uuid:draft_id>/approve/',v.approve),path('cases/<uuid:id>/drafts/<uuid:draft_id>/export/',v.export)]

from . import workflow

urlpatterns += [
    path('cases/<uuid:id>/workflow/', workflow.case_workflow),
    path('cases/<uuid:id>/assign-review/', workflow.assign_review),
    path('reviews/', workflow.review_queue),
    path('reviews/<int:task_id>/', workflow.review_item),
    path('templates/', workflow.templates),
    path('evidence-lab/', workflow.evidence_lab),
]
