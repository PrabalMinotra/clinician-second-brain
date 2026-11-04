from django.urls import include,path,re_path
from second_brain.views import frontend
urlpatterns=[path('api/second_brain/',include('second_brain.urls')),re_path(r'^(?P<path>.*)$',frontend)]
