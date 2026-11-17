from django.urls import path
from .views import (
    ProfileMeAPIView,
    StaffSelfProfileAPIView,
    StudentSelfProfileAPIView,
    ParentSelfProfileAPIView,
)

app_name = 'profile'

urlpatterns = [
    path('me/', ProfileMeAPIView.as_view(), name='profile-me'),
    path('staff/', StaffSelfProfileAPIView.as_view(), name='profile-staff'),
    path('student/', StudentSelfProfileAPIView.as_view(), name='profile-student'),
    path('parent/', ParentSelfProfileAPIView.as_view(), name='profile-parent'),
]