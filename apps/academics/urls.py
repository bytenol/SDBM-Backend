# apps/academics/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SchoolSettingsView,
    AcademicSessionViewSet,
    AcademicTermViewSet,
    ClassViewSet,
    ClassArmViewSet,
    SubjectViewSet,
    ClassSubjectViewSet
)


router = DefaultRouter()
router.register(r'sessions', AcademicSessionViewSet, basename='academic-session')
router.register(r'terms', AcademicTermViewSet, basename='academic-term')
router.register(r'classes', ClassViewSet, basename='class')
router.register(r'class-arms', ClassArmViewSet, basename='class-arm')
router.register(r'subjects', SubjectViewSet, basename='subject')
router.register(r'class-subjects', ClassSubjectViewSet, basename='class-subject')

app_name = 'academics'

urlpatterns = [
    path('settings/', SchoolSettingsView.as_view(), name='school-settings'),
    path('', include(router.urls)),
]