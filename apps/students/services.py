# apps/students/services.py
import datetime
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from apps.accounts.models import Role
from apps.academics.models import SchoolSettings
from .models import Student, StudentGuardian, StudentEnrollment

User = get_user_model()

def generate_admission_number():
    """
    Atomically generates the next unique admission number for the current year.
    Format: STU-YYYY-XXXX (e.g., STU-2026-0001)
    Uses select_for_update() to lock database rows and prevent race conditions.
    """
    current_year = datetime.date.today().year
    prefix = f"STU-{current_year}-"
    
    with transaction.atomic():
        last_user = (
            User.objects.filter(login_id__startswith=prefix)
            .select_for_update()
            .order_by('login_id')
            .last()
        )
        
        if last_user and last_user.login_id:
            try:
                last_seq = int(last_user.login_id.split('-')[-1])
                new_seq = last_seq + 1
            except ValueError:
                new_seq = 1
        else:
            new_seq = 1
            
        return f"{prefix}{new_seq:04d}"


@transaction.atomic
def provision_student_account(validated_data, admin_user=None):
    """
    Atomic operation to provision a student account:
    1. Generates unique admission number (stored in User.login_id).
    2. Creates User account with STUDENT role and temporary password.
    3. Creates Student profile linked to User.
    4. Links parents/guardians if provided.
    5. Creates initial session enrollment if class info is provided.
    """
    # Extract nested payloads if provided in serializer
    guardians_data = validated_data.pop('guardians', [])
    enrollment_data = validated_data.pop('enrollment', None)
    
    # 1. Generate atomic admission number
    admission_number = generate_admission_number()
    
    # 2. Generate secure temporary password
    temp_password = get_random_string(length=12)
    
    # 3. Create User account
    user = User.objects.create_user(
        login_id=admission_number,
        email=validated_data.get('email'),
        password=temp_password,
        first_name=validated_data['first_name'],
        last_name=validated_data['last_name'],
        is_active=True,
        is_verified=True if validated_data.get('email') else False
    )
    
    # 4. Assign STUDENT role
    student_role = Role.objects.get(name=Role.RoleChoices.STUDENT)
    user.roles.add(student_role)
    
    # 5. Create Student Profile
    student = Student.objects.create(
        user=user,
        first_name=validated_data['first_name'],
        middle_name=validated_data.get('middle_name', ''),
        last_name=validated_data['last_name'],
        date_of_birth=validated_data['date_of_birth'],
        gender=validated_data['gender'],
        nationality=validated_data.get('nationality', 'Nigerian'),
        state_of_origin=validated_data.get('state_of_origin', ''),
        lga=validated_data.get('lga', ''),
        residential_address=validated_data.get('residential_address', ''),
        admission_date=validated_data.get('admission_date', datetime.date.today()),
        status='ACTIVE',
        medical_info=validated_data.get('medical_info', ''),
        administrative_notes=validated_data.get('administrative_notes', '')
    )
    
    if 'passport_photograph' in validated_data and validated_data['passport_photograph']:
        student.passport_photograph = validated_data['passport_photograph']
        student.save(update_fields=['passport_photograph'])
        
    # 6. Link Guardians if provided
    for guardian_info in guardians_data:
        StudentGuardian.objects.create(
            student=student,
            guardian=guardian_info['guardian'],
            relationship_type=guardian_info.get('relationship_type', StudentGuardian.RelationshipChoices.FATHER),
            is_primary=guardian_info.get('is_primary', False),
            is_emergency_contact=guardian_info.get('is_emergency_contact', False),
            can_collect_student=guardian_info.get('can_collect_student', True),
            receives_notifications=guardian_info.get('receives_notifications', True)
        )
        
    # 7. Establish Initial Student Enrollment
    settings_obj = SchoolSettings.load()
    session = settings_obj.current_session
    term = settings_obj.current_term
    
    if enrollment_data and session:
        StudentEnrollment.objects.create(
            student=student,
            academic_session=session,
            academic_term=term,
            class_obj=enrollment_data['class_obj'],
            class_arm=enrollment_data.get('class_arm'),
            enrollment_date=student.admission_date,
            status='ENROLLED',
            enrollment_type='NEW_ADMISSION',
            remarks=enrollment_data.get('remarks', 'Initial admission enrollment.')
        )
        
    return student, temp_password