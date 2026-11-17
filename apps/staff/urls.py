from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DepartmentViewSet,
    DesignationViewSet,
    StaffViewSet,
    TeacherAssignmentViewSet
)

router = DefaultRouter()
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'designations', DesignationViewSet, basename='designation')
router.register(r'assignments', TeacherAssignmentViewSet, basename='teacher-assignment')
router.register(r'', StaffViewSet, basename='staff')

app_name = 'staff'

urlpatterns = [
    path('', include(router.urls)),
]