# apps/dashboard/urls.py
from django.urls import path
from .views import (
    AdminDashboardAPIView,
    StaffDashboardAPIView,
    StudentDashboardAPIView,
    ParentDashboardAPIView,
    AcademicOverviewAPIView,
    EnrollmentAnalyticsAPIView,
    StaffAnalyticsAPIView,
    ResultAnalyticsAPIView,
)

app_name = 'dashboard'

urlpatterns = [
    # Role-Specific Portal Dashboards
    path('admin/', AdminDashboardAPIView.as_view(), name='dashboard-admin'),
    path('staff/', StaffDashboardAPIView.as_view(), name='dashboard-staff'),
    path('student/', StudentDashboardAPIView.as_view(), name='dashboard-student'),
    path('parent/', ParentDashboardAPIView.as_view(), name='dashboard-parent'),

    # Academic Overview (Role-Scoped)
    path('academic-overview/', AcademicOverviewAPIView.as_view(), name='dashboard-academic-overview'),

    # Administrator Deep Analytics
    path('analytics/enrollments/', EnrollmentAnalyticsAPIView.as_view(), name='dashboard-analytics-enrollments'),
    path('analytics/staff/', StaffAnalyticsAPIView.as_view(), name='dashboard-analytics-staff'),
    path('analytics/results/', ResultAnalyticsAPIView.as_view(), name='dashboard-analytics-results'),
]