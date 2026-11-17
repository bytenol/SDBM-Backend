from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Role
from django.utils.crypto import get_random_string
from .utils import generate_login_id

User = get_user_model()


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name', 'description']



class UserSerializer(serializers.ModelSerializer):
    roles = RoleSerializer(many=True, read_only=True)
    role_names = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = ['id', 'login_id', 'email', 'first_name', 'last_name', 'is_verified', 'roles', 'role_names']
        read_only_fields = ['id', 'login_id', 'email', 'is_verified', 'roles', 'role_names']



class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True, help_text="Login ID (Students/Staff) or Email (Parents/Admins)")
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        request = self.context.get('request')
        user = authenticate(request=request, username=username, password=password)

        if not user:
            raise serializers.ValidationError('Invalid login credentials or inactive account.')

        if not user.is_active:
            raise serializers.ValidationError('This account has been disabled.')

        refresh = RefreshToken.for_user(user)

        attrs['user'] = user
        attrs['tokens'] = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
        return attrs



class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True, help_text="Refresh token to blacklist")

    def validate(self, attrs):
        self.token = attrs['refresh']
        return attrs

    def save(self, **kwargs):
        try:
            RefreshToken(self.token).blacklist()
        except Exception:
            raise serializers.ValidationError({'refresh': 'Invalid or expired refresh token.'})



class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=10)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user




class AccountProvisioningSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Role.RoleChoices.choices, required=True)
    first_name = serializers.CharField(max_length=150, required=True)
    last_name = serializers.CharField(max_length=150, required=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        role_name = attrs.get('role')
        email = attrs.get('email')

        # Parents and Admins require email
        if role_name in ['PARENT', 'ADMIN', 'SUPER_ADMIN'] and not email:
            raise serializers.ValidationError({"email": "Email is required for Parents and Administrators."})
        
        if email and User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError({"email": "A user with this email already exists."})

        return attrs

    def save(self):
        data = self.validated_data
        role_name = data['role']
        email = data.get('email')
        
        # Generate login_id for students, staff, and admins; parents use email
        login_id = None
        if role_name in ['STUDENT', 'STAFF', 'ADMIN', 'SUPER_ADMIN']:
            login_id = generate_login_id(role_name)

        # Generate a secure random temporary password
        temp_password = get_random_string(length=12)

        user = User.objects.create_user(
            login_id=login_id,
            email=email,
            password=temp_password,
            first_name=data['first_name'],
            last_name=data['last_name'],
            is_active=True,
            is_verified=True if email else False
        )

        # Assign role
        role_obj = Role.objects.get(name=role_name)
        user.roles.add(role_obj)

        return user, temp_password