# apps/accounts/backends.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


User = get_user_model()


class MultiTypeAuthBackend(ModelBackend):
    """
    Custom authentication backend supporting dual identification:
    - Email-based authentication for Parents and Administrators (contains '@')
    - Generated ID-based authentication for Students and Staff (login_id)
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        
        if not username or not password:
            return None

        try:
            # If the login string contains '@', treat it as an email (Parents/Admins)
            if '@' in username:
                user = User.objects.get(email__iexact=username)
            # Otherwise, treat it as a custom login ID (Students/Staff)
            else:
                user = User.objects.get(login_id__iexact=username)
        except User.DoesNotExist:
            # Run the default password hasher once to mitigate timing attacks against usernames/emails
            User().set_password(password)
            return None

        # Verify password and check if the user is active/can authenticate
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
            
        return None