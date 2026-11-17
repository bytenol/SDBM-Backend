import datetime
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from apps.accounts.models import Role
from .models import Staff, StaffEmployment, Department, Designation

User = get_user_model()

def generate_staff_identifier():
    """
    Atomically generates the next unique staff identifier for the current year.
    Format: STF-YYYY-XXXX (e.g., STF-2026-0001)
    Uses select_for_update() to lock database rows and prevent race conditions.
    """
    current_year = datetime.date.today().year
    prefix = f"STF-{current_year}-"
    
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
def provision_staff_account(validated_data, admin_user=None):
    """
    Atomic operation to provision a staff account:
    1. Generates unique staff identifier (stored in User.login_id).
    2. Creates User account with STAFF role and temporary password.
    3. Creates Staff profile linked to User.
    4. Creates initial employment record if department and designation are provided.
    """
    employment_data = validated_data.pop('employment', None)
    
    # 1. Generate atomic staff ID
    staff_id = generate_staff_identifier()
    
    # 2. Generate secure temporary password
    temp_password = get_random_string(length=12)
    
    # 3. Create User account
    user = User.objects.create_user(
        login_id=staff_id,
        email=validated_data.get('email'),
        password=temp_password,
        first_name=validated_data['first_name'],
        last_name=validated_data['last_name'],
        is_active=True,
        is_verified=True if validated_data.get('email') else False
    )
    
    # 4. Assign STAFF role
    staff_role = Role.objects.get(name=Role.RoleChoices.STAFF)
    user.roles.add(staff_role)
    
    # 5. Create Staff Profile
    staff = Staff.objects.create(
        user=user,
        first_name=validated_data['first_name'],
        middle_name=validated_data.get('middle_name', ''),
        last_name=validated_data['last_name'],
        date_of_birth=validated_data.get('date_of_birth'),
        gender=validated_data['gender'],
        nationality=validated_data.get('nationality', 'Nigerian'),
        state_of_origin=validated_data.get('state_of_origin', ''),
        lga=validated_data.get('lga', ''),
        residential_address=validated_data.get('residential_address', ''),
        phone_number=validated_data.get('phone_number', ''),
        emergency_contact_name=validated_data.get('emergency_contact_name', ''),
        emergency_contact_phone=validated_data.get('emergency_contact_phone', ''),
        emergency_contact_relationship=validated_data.get('emergency_contact_relationship', ''),
        bio=validated_data.get('bio', ''),
        administrative_notes=validated_data.get('administrative_notes', '')
    )
    
    if 'passport_photograph' in validated_data and validated_data['passport_photograph']:
        staff.passport_photograph = validated_data['passport_photograph']
        staff.save(update_fields=['passport_photograph'])
        
    # 6. Create Initial Employment Record if provided
    if employment_data:
        dept_id = employment_data.get('department')
        desig_id = employment_data.get('designation')
        
        department = Department.objects.get(pk=dept_id)
        designation = Designation.objects.get(pk=desig_id)
        
        StaffEmployment.objects.create(
            staff=staff,
            department=department,
            designation=designation,
            employment_type=employment_data.get('employment_type', StaffEmployment.EmploymentType.FULL_TIME),
            start_date=employment_data.get('start_date', datetime.date.today()),
            status=StaffEmployment.EmploymentStatus.ACTIVE,
            remarks=employment_data.get('remarks', 'Initial staff employment record.')
        )
        
    return staff, temp_password