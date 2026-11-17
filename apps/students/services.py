import datetime
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from apps.accounts.models import Role
from apps.academics.models import AcademicSession, SchoolSettings
from .models import Student, StudentGuardian, StudentEnrollment
from apps.academics.models import SchoolSettings, Class, ClassArm
from .models import StudentPromotionLog
from django.core.exceptions import ValidationError


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
        
    # 7. Establish Initial Student Enrollment (Resolving UUID strings to model instances)
    settings_obj = SchoolSettings.load()
    session = settings_obj.current_session
    term = settings_obj.current_term
    
    if enrollment_data and session:
        class_obj_id = enrollment_data.get('class_obj')
        class_arm_id = enrollment_data.get('class_arm')
        
        class_instance = Class.objects.get(pk=class_obj_id)
        class_arm_instance = ClassArm.objects.filter(pk=class_arm_id).first() if class_arm_id else None
        
        StudentEnrollment.objects.create(
            student=student,
            academic_session=session,
            academic_term=term,
            class_obj=class_instance,
            class_arm=class_arm_instance,
            enrollment_date=student.admission_date,
            status='ENROLLED',
            enrollment_type='NEW_ADMISSION',
            remarks=enrollment_data.get('remarks', 'Initial admission enrollment.')
        )
        
    return student, temp_password




@transaction.atomic
def promote_students_service(validated_data, admin_user=None):
    """
    Atomically promotes a list of students from a source session to a destination session/class:
    1. Validates source session, destination session, class, and optional arm.
    2. Ensures students have an enrollment in the source session.
    3. Prevents duplicate enrollments in the destination session.
    4. Creates new StudentEnrollment records with type 'PROMOTION'.
    5. Creates a StudentPromotionLog audit record.
    """
    source_session_id = validated_data['source_session']
    destination_session_id = validated_data['destination_session']
    student_ids = validated_data['student_ids']
    destination_class_id = validated_data['destination_class']
    destination_class_arm_id = validated_data.get('destination_class_arm')
    remarks = validated_data.get('remarks', 'Promoted to new academic session.')

    # 1. Fetch related objects
    source_session = AcademicSession.objects.get(pk=source_session_id)
    destination_session = AcademicSession.objects.get(pk=destination_session_id)
    destination_class = Class.objects.get(pk=destination_class_id)
    
    destination_arm = None
    if destination_class_arm_id:
        destination_arm = ClassArm.objects.get(pk=destination_class_arm_id)
        if destination_arm.class_obj != destination_class:
            raise ValidationError("The selected class arm does not belong to the destination class.")

    promoted_count = 0
    today = datetime.date.today()

    for student_id in student_ids:
        student = Student.objects.get(pk=student_id)

        # Verify student was enrolled in the source session
        source_enrollment = StudentEnrollment.objects.filter(
            student=student,
            academic_session=source_session
        ).first()

        if not source_enrollment:
            raise ValidationError(f"Student {student} is not enrolled in the source session ({source_session.name}).")

        # Mark source enrollment as completed
        source_enrollment.status = StudentEnrollment.EnrollmentStatus.COMPLETED
        source_enrollment.save(update_fields=['status'])

        # Check if already enrolled in destination session
        dest_enrollment, created = StudentEnrollment.objects.get_or_create(
            student=student,
            academic_session=destination_session,
            defaults={
                'academic_term': destination_session.terms.filter(name='FIRST').first() or destination_session.terms.first(),
                'class_obj': destination_class,
                'class_arm': destination_arm,
                'enrollment_date': today,
                'status': StudentEnrollment.EnrollmentStatus.ENROLLED,
                'enrollment_type': StudentEnrollment.EnrollmentType.PROMOTION,
                'remarks': remarks
            }
        )

        if not created:
            # Update existing destination enrollment if re-running or adjusting
            dest_enrollment.class_obj = destination_class
            dest_enrollment.class_arm = destination_arm
            dest_enrollment.status = StudentEnrollment.EnrollmentStatus.ENROLLED
            dest_enrollment.enrollment_type = StudentEnrollment.EnrollmentType.PROMOTION
            dest_enrollment.remarks = remarks
            dest_enrollment.save()

        promoted_count += 1

    # 2. Create promotion audit log
    log = StudentPromotionLog.objects.create(
        source_session=source_session,
        destination_session=destination_session,
        destination_class=destination_class,
        destination_class_arm=destination_arm,
        promoted_students_count=promoted_count,
        promoted_by=admin_user,
        remarks=remarks
    )

    return log, promoted_count