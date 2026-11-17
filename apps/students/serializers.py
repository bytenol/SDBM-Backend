from rest_framework import serializers
from apps.accounts.serializers import UserSerializer
from apps.academics.serializers import AcademicSessionSerializer, ClassSerializer, ClassArmSerializer
from .models import Student, StudentGuardian, StudentEnrollment, StudentDocument
from .services import promote_students_service, provision_student_account

class StudentGuardianSerializer(serializers.ModelSerializer):
    guardian_details = UserSerializer(source='guardian', read_only=True)
    guardian_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = StudentGuardian
        fields = [
            'id', 'student', 'guardian_id', 'guardian_details',
            'relationship_type', 'is_primary', 'is_emergency_contact',
            'can_collect_student', 'receives_notifications', 'created_at'
        ]
        read_only_fields = ['id', 'student', 'created_at']


class StudentEnrollmentSerializer(serializers.ModelSerializer):
    academic_session_details = AcademicSessionSerializer(source='academic_session', read_only=True)
    class_details = ClassSerializer(source='class_obj', read_only=True)
    class_arm_details = ClassArmSerializer(source='class_arm', read_only=True)
    
    class_obj = serializers.UUIDField(write_only=True)
    class_arm = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = StudentEnrollment
        fields = [
            'id', 'student', 'academic_session', 'academic_session_details',
            'academic_term', 'class_obj', 'class_details', 'class_arm',
            'class_arm_details', 'enrollment_date', 'status', 'enrollment_type',
            'remarks', 'created_at'
        ]
        read_only_fields = ['id', 'student', 'academic_session', 'created_at']


class StudentDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.ReadOnlyField(source='uploaded_by.get_full_name')

    class Meta:
        model = StudentDocument
        fields = ['id', 'student', 'document_type', 'file', 'description', 'uploaded_by', 'uploaded_by_name', 'created_at']
        read_only_fields = ['id', 'student', 'uploaded_by', 'created_at']

    def validate_file(self, value):
        max_size = 5 * 1024 * 1024  # 5MB limit
        if value.size > max_size:
            raise serializers.ValidationError("File size cannot exceed 5MB.")
        return value


class StudentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    admission_number = serializers.CharField(source='user.login_id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    guardians = StudentGuardianSerializer(many=True, read_only=True)
    enrollments = StudentEnrollmentSerializer(many=True, read_only=True)
    documents = StudentDocumentSerializer(many=True, read_only=True)
    gender_display = serializers.CharField(source='get_gender_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Student
        fields = [
            'id', 'user', 'admission_number', 'email', 'first_name', 'middle_name',
            'last_name', 'date_of_birth', 'gender', 'gender_display',
            'passport_photograph', 'nationality', 'state_of_origin', 'lga',
            'residential_address', 'admission_date', 'status', 'status_display',
            'medical_info', 'administrative_notes', 'guardians', 'enrollments',
            'documents', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'admission_number', 'email', 'created_at', 'updated_at']


class InitialEnrollmentInputSerializer(serializers.Serializer):
    class_obj = serializers.UUIDField(required=True)
    class_arm = serializers.UUIDField(required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True)


class GuardianInputSerializer(serializers.Serializer):
    guardian = serializers.UUIDField(required=True)
    relationship_type = serializers.CharField(required=True)
    is_primary = serializers.BooleanField(default=False)
    is_emergency_contact = serializers.BooleanField(default=False)


class StudentProvisioningSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=True)
    middle_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    date_of_birth = serializers.DateField(required=True)
    gender = serializers.ChoiceField(choices=Student.GenderChoices.choices, required=True)
    passport_photograph = serializers.ImageField(required=False, allow_null=True)
    nationality = serializers.CharField(max_length=100, default='Nigerian', required=False)
    state_of_origin = serializers.CharField(max_length=100, required=False, allow_blank=True)
    lga = serializers.CharField(max_length=100, required=False, allow_blank=True)
    residential_address = serializers.CharField(required=False, allow_blank=True)
    admission_date = serializers.DateField(required=False)
    medical_info = serializers.CharField(required=False, allow_blank=True)
    administrative_notes = serializers.CharField(required=False, allow_blank=True)
    
    guardians = GuardianInputSerializer(many=True, required=False)
    enrollment = InitialEnrollmentInputSerializer(required=False, allow_null=True)

    def save(self, admin_user=None):
        # Calls our atomic provisioning service
        student, temp_password = provision_student_account(self.validated_data, admin_user)
        return student, temp_password



class StudentPromotionSerializer(serializers.Serializer):
    source_session = serializers.UUIDField(required=True)
    destination_session = serializers.UUIDField(required=True)
    student_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True,
        min_length=1,
        help_text="List of student UUIDs to promote"
    )
    destination_class = serializers.UUIDField(required=True)
    destination_class_arm = serializers.UUIDField(required=False, allow_null=True)
    remarks = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs['source_session'] == attrs['destination_session']:
            raise serializers.ValidationError("Source and destination academic sessions cannot be the same.")
        return attrs

    def save(self, admin_user=None):
        return promote_students_service(self.validated_data, admin_user)