from rest_framework import serializers
from apps.accounts.serializers import UserSerializer
from apps.academics.serializers import AcademicSessionSerializer, ClassSerializer, ClassArmSerializer, SubjectSerializer
from .models import (
    Department,
    Designation,
    Staff,
    StaffEmployment,
    TeacherAssignment,
    StaffQualification,
    StaffDocument
)
from .services import provision_staff_account


class DepartmentSerializer(serializers.ModelSerializer):
    head_name = serializers.ReadOnlyField(source='head.__str__')

    class Meta:
        model = Department
        fields = ['id', 'name', 'code', 'description', 'head', 'head_name', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class DesignationSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = Designation
        fields = ['id', 'name', 'code', 'category', 'category_display', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class StaffEmploymentSerializer(serializers.ModelSerializer):
    department_details = DepartmentSerializer(source='department', read_only=True)
    designation_details = DesignationSerializer(source='designation', read_only=True)
    department = serializers.UUIDField(write_only=True)
    designation = serializers.UUIDField(write_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = StaffEmployment
        fields = [
            'id', 'staff', 'department', 'department_details',
            'designation', 'designation_details', 'employment_type',
            'start_date', 'end_date', 'status', 'status_display',
            'remarks', 'created_at'
        ]
        read_only_fields = ['id', 'staff', 'created_at']


class TeacherAssignmentSerializer(serializers.ModelSerializer):
    academic_session_details = AcademicSessionSerializer(source='academic_session', read_only=True)
    class_details = ClassSerializer(source='class_obj', read_only=True)
    class_arm_details = ClassArmSerializer(source='class_arm', read_only=True)
    subject_details = SubjectSerializer(source='subject', read_only=True)
    staff_name = serializers.ReadOnlyField(source='staff.__str__')

    academic_session = serializers.UUIDField(write_only=True)
    class_obj = serializers.UUIDField(write_only=True)
    class_arm = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    subject = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = TeacherAssignment
        fields = [
            'id', 'staff', 'staff_name', 'academic_session', 'academic_session_details',
            'class_obj', 'class_details', 'class_arm', 'class_arm_details',
            'subject', 'subject_details', 'assignment_type', 'is_class_teacher',
            'is_active', 'remarks', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class StaffQualificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffQualification
        fields = [
            'id', 'staff', 'qualification_name', 'institution',
            'field_of_study', 'qualification_level', 'start_year',
            'completion_year', 'certificate_document', 'created_at'
        ]
        read_only_fields = ['id', 'staff', 'created_at']


class StaffDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.ReadOnlyField(source='uploaded_by.get_full_name')

    class Meta:
        model = StaffDocument
        fields = ['id', 'staff', 'document_type', 'file', 'description', 'uploaded_by', 'uploaded_by_name', 'created_at']
        read_only_fields = ['id', 'staff', 'uploaded_by', 'created_at']

    def validate_file(self, value):
        max_size = 5 * 1024 * 1024  # 5MB limit
        if value.size > max_size:
            raise serializers.ValidationError("File size cannot exceed 5MB.")
        return value


class StaffSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    staff_id = serializers.CharField(source='user.login_id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    employment_records = StaffEmploymentSerializer(many=True, read_only=True)
    teaching_assignments = TeacherAssignmentSerializer(many=True, read_only=True)
    qualifications = StaffQualificationSerializer(many=True, read_only=True)
    documents = StaffDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Staff
        fields = [
            'id', 'user', 'staff_id', 'email', 'first_name', 'middle_name',
            'last_name', 'date_of_birth', 'gender', 'passport_photograph',
            'nationality', 'state_of_origin', 'lga', 'residential_address',
            'phone_number', 'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relationship', 'bio', 'administrative_notes',
            'employment_records', 'teaching_assignments', 'qualifications',
            'documents', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'staff_id', 'email', 'created_at', 'updated_at']


class InitialEmploymentInputSerializer(serializers.Serializer):
    department = serializers.UUIDField(required=True)
    designation = serializers.UUIDField(required=True)
    employment_type = serializers.CharField(default='FULL_TIME', required=False)
    start_date = serializers.DateField(required=False)
    remarks = serializers.CharField(required=False, allow_blank=True)


class StaffProvisioningSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=True)
    middle_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=[('MALE', 'Male'), ('FEMALE', 'Female')], required=True)
    passport_photograph = serializers.ImageField(required=False, allow_null=True)
    nationality = serializers.CharField(max_length=100, default='Nigerian', required=False)
    state_of_origin = serializers.CharField(max_length=100, required=False, allow_blank=True)
    lga = serializers.CharField(max_length=100, required=False, allow_blank=True)
    residential_address = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    emergency_contact_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    emergency_contact_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    emergency_contact_relationship = serializers.CharField(max_length=100, required=False, allow_blank=True)
    bio = serializers.CharField(required=False, allow_blank=True)
    administrative_notes = serializers.CharField(required=False, allow_blank=True)
    
    employment = InitialEmploymentInputSerializer(required=False, allow_null=True)

    def save(self, admin_user=None):
        staff, temp_password = provision_staff_account(self.validated_data, admin_user)
        return staff, temp_password