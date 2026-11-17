from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.staff.models import Staff
from apps.staff.serializers import (
    StaffEmploymentSerializer,
    TeacherAssignmentSerializer,
    StaffQualificationSerializer,
)
from apps.students.models import Student, StudentEnrollment, StudentGuardian

User = get_user_model()



class DashboardContextFilterSerializer(serializers.Serializer):
    """
    Validates optional session_id, term_id, student_id, class_id, and refresh parameters on dashboard endpoints.
    """
    session_id = serializers.UUIDField(required=False)
    term_id = serializers.UUIDField(required=False)
    student_id = serializers.UUIDField(required=False)
    class_id = serializers.UUIDField(required=False)
    refresh = serializers.BooleanField(required=False, default=False)


class AccountMeUpdateSerializer(serializers.ModelSerializer):
    """
    Allows an authenticated user to update only their safe contact/display fields on /api/v1/profile/me/.
    login_id, roles, is_active, and password are strictly excluded.
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def validate_email(self, value):
        if value:
            qs = User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("A user with this email address already exists.")
        return value


class StaffSelfProfileSerializer(serializers.ModelSerializer):
    """
    Staff self-service profile serializer for /api/v1/profile/staff/.
    Excludes confidential administrative_notes and prevents staff from altering
    their staff_id, employment status, or designations.
    """
    staff_id = serializers.ReadOnlyField(source='user.login_id')
    email = serializers.ReadOnlyField(source='user.email')
    headed_departments = serializers.SerializerMethodField()
    employment_records = StaffEmploymentSerializer(many=True, read_only=True)
    teaching_assignments = TeacherAssignmentSerializer(many=True, read_only=True)
    qualifications = StaffQualificationSerializer(many=True, read_only=True)

    class Meta:
        model = Staff
        fields = [
            'id', 'staff_id', 'email', 'first_name', 'middle_name', 'last_name',
            'date_of_birth', 'gender', 'passport_photograph', 'nationality',
            'state_of_origin', 'lga', 'residential_address', 'phone_number',
            'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relationship', 'bio', 'headed_departments',
            'employment_records', 'teaching_assignments', 'qualifications',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'staff_id', 'email', 'first_name', 'middle_name', 'last_name',
            'date_of_birth', 'gender', 'nationality', 'state_of_origin', 'lga',
            'headed_departments', 'employment_records', 'teaching_assignments',
            'qualifications', 'created_at', 'updated_at',
        ]

    def get_headed_departments(self, obj):
        return [
            {"id": str(dept.id), "name": dept.name, "code": dept.code}
            for dept in obj.headed_departments.filter(is_active=True)
        ]


class StudentEnrollmentSummarySerializer(serializers.ModelSerializer):
    session_name = serializers.ReadOnlyField(source='academic_session.name')
    term_name = serializers.ReadOnlyField(source='academic_term.get_name_display')
    class_name = serializers.ReadOnlyField(source='class_obj.name')
    class_arm_name = serializers.ReadOnlyField(source='class_arm.name')

    class Meta:
        model = StudentEnrollment
        fields = [
            'id', 'academic_session', 'session_name', 'academic_term', 'term_name',
            'class_obj', 'class_name', 'class_arm', 'class_arm_name',
            'enrollment_date', 'status', 'enrollment_type',
        ]
        read_only_fields = fields



class StudentGuardianSummarySerializer(serializers.ModelSerializer):
    guardian_name = serializers.SerializerMethodField()
    guardian_email = serializers.SerializerMethodField()
    guardian_login_id = serializers.SerializerMethodField()
    relationship = serializers.SerializerMethodField()
    is_primary = serializers.SerializerMethodField()

    class Meta:
        model = StudentGuardian
        fields = [
            'id',
            'guardian_login_id',
            'guardian_name',
            'guardian_email',
            'relationship',
            'is_primary',
        ]
        read_only_fields = fields

    def _get_guardian_user(self, obj):
        guardian = getattr(obj, 'guardian', None) or getattr(obj, 'parent', None) or getattr(obj, 'user', None)
        if hasattr(guardian, 'user') and guardian.user is not None:
            return guardian.user
        return guardian

    def get_guardian_name(self, obj) -> str:
        guardian = getattr(obj, 'guardian', None) or getattr(obj, 'parent', None)
        if guardian and hasattr(guardian, 'first_name'):
            return f"{guardian.first_name} {guardian.last_name}".strip()
        user = self._get_guardian_user(obj)
        if user and hasattr(user, 'first_name'):
            return f"{user.first_name} {user.last_name}".strip()
        return str(guardian or "")

    def get_guardian_email(self, obj):
        user = self._get_guardian_user(obj)
        return getattr(user, 'email', None)

    def get_guardian_login_id(self, obj):
        user = self._get_guardian_user(obj)
        return getattr(user, 'login_id', None)

    def get_relationship(self, obj):
        return (
            getattr(obj, 'relationship', None)
            or getattr(obj, 'relationship_type', None)
            or getattr(obj, 'relation', None)
            or 'GUARDIAN'
        )

    def get_is_primary(self, obj) -> bool:
        return bool(
            getattr(obj, 'is_primary', False)
            or getattr(obj, 'is_primary_guardian', False)
            or getattr(obj, 'is_emergency_contact', False)
        )

class StudentSelfProfileSerializer(serializers.ModelSerializer):
    """
    Read-only student self-profile serializer for /api/v1/profile/student/.
    """
    admission_number = serializers.ReadOnlyField(source='user.login_id')
    email = serializers.ReadOnlyField(source='user.email')
    enrollments = StudentEnrollmentSummarySerializer(many=True, read_only=True)
    guardians = StudentGuardianSummarySerializer(many=True, read_only=True)

    class Meta:
        model = Student
        fields = [
            'id', 'admission_number', 'email', 'first_name', 'middle_name',
            'last_name', 'date_of_birth', 'gender', 'passport_photograph',
            'nationality', 'state_of_origin', 'lga', 'residential_address',
            'enrollments', 'guardians', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class ParentProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Allows a parent to update their safe contact details on /api/v1/profile/parent/.
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']