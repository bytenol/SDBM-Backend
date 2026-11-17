import uuid
from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    
    """
    Custom user manager where either login_id or email can be used for identification.
    """
    def create_user(self, login_id=None, email=None, password=None, **extra_fields):
        if not login_id and not email:
            raise ValueError('Users must have either a login_id or an email address.')

        if email:
            email = self.normalize_email(email)
        
        # Django's AbstractUser requires a username field; we auto-generate one if not provided
        if 'username' not in extra_fields or not extra_fields['username']:
            extra_fields['username'] = str(uuid.uuid4())

        user = self.model(login_id=login_id, email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user


    def create_superuser(self, login_id=None, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_verified', True)

        if not email and not login_id:
            raise ValueError('Superuser must have an email or login_id.')

        if email and not login_id:
            login_id = 'ADMIN-' + str(uuid.uuid4())[:8].upper()

        user = self.create_user(login_id=login_id, email=email, password=password, **extra_fields)
        return user