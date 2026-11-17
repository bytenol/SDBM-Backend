from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    AccountProvisioningView,
    LoginView,
    LogoutView,
    UserProfileView,
    ChangePasswordView
)

app_name = 'accounts'


urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', UserProfileView.as_view(), name='user_profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('provision/', AccountProvisioningView.as_view(), name='provision_account'),
]