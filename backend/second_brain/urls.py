from django.urls import path
from . import views as v
urlpatterns=[path('cases/<uuid:id>/query/',v.query_history),path('session/',v.session),path('cases/',v.cases),path('cases/<uuid:id>/',v.case_detail),path('cases/<uuid:id>/intake/',v.intake),path('cases/<uuid:id>/sources/<uuid:source_id>/',v.review_source),path('cases/<uuid:id>/generate/',v.generate),path('cases/<uuid:id>/drafts/<uuid:draft_id>/',v.edit_draft),path('cases/<uuid:id>/drafts/<uuid:draft_id>/approve/',v.approve),path('cases/<uuid:id>/drafts/<uuid:draft_id>/export/',v.export)]
