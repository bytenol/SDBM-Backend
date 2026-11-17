from django.db.models import Prefetch
from apps.academics.models import SchoolSettings
from apps.students.models import Student, StudentEnrollment, StudentGuardian
from apps.staff.models import Staff, StaffEmployment, TeacherAssignment


def get_active_school_context() -> dict:
    """
    Returns the active academic session and term configured in SchoolSettings.
    """
    settings_obj = SchoolSettings.load()
    session = settings_obj.current_session
    term = settings_obj.current_term
    return {
        "school_name": getattr(settings_obj, 'school_name', 'Almawrid Islamic International College'),
        "school_motto": getattr(settings_obj, 'school_motto', ''),
        "current_session": {
            "id": str(session.id),
            "name": session.name,
            "start_date": str(session.start_date),
            "end_date": str(session.end_date),
        } if session else None,
        "current_term": {
            "id": str(term.id),
            "name": term.name,
            "display_name": term.get_name_display(),
            "start_date": str(term.start_date),
            "end_date": str(term.end_date),
        } if term else None,
    }


def resolve_primary_portal(role_names: list[str], is_superuser: bool) -> str:
    """
    Determines the primary frontend portal route based on role priority.
    Priority: SUPER_ADMIN / ADMIN -> STAFF -> STUDENT -> PARENT
    """
    if is_superuser or 'SUPER_ADMIN' in role_names or 'ADMIN' in role_names:
        return 'ADMIN'
    if 'STAFF' in role_names:
        return 'STAFF'
    if 'STUDENT' in role_names:
        return 'STUDENT'
    if 'PARENT' in role_names:
        return 'PARENT'
    return 'GENERAL'


def build_consolidated_me_payload(user) -> dict:
    """
    Constructs the /api/v1/profile/me/ payload for any authenticated user.
    Never exposes password hashes, refresh tokens, or internal administrative notes.
    """
    role_names = list(user.roles.values_list('name', flat=True))
    has_staff = hasattr(user, 'staff_profile') and user.staff_profile is not None
    has_student = hasattr(user, 'student_profile') and user.student_profile is not None
    linked_children_count = StudentGuardian.objects.filter(guardian=user).count()

    available_portals = []
    if user.is_superuser or 'SUPER_ADMIN' in role_names or 'ADMIN' in role_names:
        available_portals.append('ADMIN')
    if 'STAFF' in role_names and has_staff:
        available_portals.append('STAFF')
    if 'STUDENT' in role_names and has_student:
        available_portals.append('STUDENT')
    if 'PARENT' in role_names or linked_children_count > 0:
        available_portals.append('PARENT')

    profile_summary = {}
    if has_staff:
        staff = user.staff_profile
        active_emp = (
            StaffEmployment.objects.filter(staff=staff, status=StaffEmployment.EmploymentStatus.ACTIVE)
            .select_related('department', 'designation')
            .first()
        )
        profile_summary['staff'] = {
            "profile_id": str(staff.id),
            "staff_id": user.login_id,
            "full_name": f"{staff.last_name}, {staff.first_name} {staff.middle_name or ''}".strip(),
            "department": active_emp.department.name if active_emp else None,
            "designation": active_emp.designation.name if active_emp else None,
            "category": active_emp.designation.category if active_emp else None,
        }

    if has_student:
        student = user.student_profile
        settings_obj = SchoolSettings.load()
        current_enrollment = (
            StudentEnrollment.objects.filter(
                student=student,
                academic_session=settings_obj.current_session
            )
            .select_related('class_obj', 'class_arm', 'academic_session')
            .first()
        ) or (
            StudentEnrollment.objects.filter(student=student)
            .select_related('class_obj', 'class_arm', 'academic_session')
            .order_by('-created_at')
            .first()
        )
        profile_summary['student'] = {
            "profile_id": str(student.id),
            "admission_number": user.login_id,
            "full_name": f"{student.last_name}, {student.first_name} {student.middle_name or ''}".strip(),
            "current_class": current_enrollment.class_obj.name if current_enrollment else None,
            "current_class_arm": current_enrollment.class_arm.name if (current_enrollment and current_enrollment.class_arm) else None,
            "enrollment_status": current_enrollment.status if current_enrollment else None,
        }

    if linked_children_count > 0 or 'PARENT' in role_names:
        profile_summary['parent'] = {
            "linked_children_count": linked_children_count,
        }

    return {
        "account": {
            "id": str(user.id),
            "login_id": user.login_id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "full_name": f"{user.first_name} {user.last_name}".strip(),
            "is_active": user.is_active,
            "is_verified": getattr(user, 'is_verified', True),
            "roles": role_names,
            "primary_portal": resolve_primary_portal(role_names, user.is_superuser),
            "available_portals": available_portals,
            "last_login": user.last_login.isoformat() if user.last_login else None,
        },
        "profiles": {
            "has_staff_profile": has_staff,
            "has_student_profile": has_student,
            "is_parent": linked_children_count > 0 or 'PARENT' in role_names,
            "summary": profile_summary,
        },
        "school_context": get_active_school_context(),
    }


def get_staff_self_profile(user) -> Staff:
    """
    Fetches the authenticated staff member's profile with prefetched employment,
    active session teaching assignments, and qualifications.
    """
    settings_obj = SchoolSettings.load()
    assignments_qs = TeacherAssignment.objects.select_related(
        'academic_session', 'class_obj', 'class_arm', 'subject'
    ).filter(is_active=True)
    if settings_obj.current_session:
        assignments_qs = assignments_qs.filter(academic_session=settings_obj.current_session)

    return (
        Staff.objects.select_related('user')
        .prefetch_related(
            Prefetch(
                'employment_records',
                queryset=StaffEmployment.objects.select_related('department', 'designation').order_by('-start_date')
            ),
            Prefetch('teaching_assignments', queryset=assignments_qs),
            'qualifications',
            'headed_departments',
        )
        .get(user=user)
    )


def get_student_self_profile(user) -> Student:
    """
    Fetches the authenticated student's profile with prefetched enrollments and guardians.
    """
    return (
        Student.objects.select_related('user')
        .prefetch_related(
            Prefetch(
                'enrollments',
                queryset=StudentEnrollment.objects.select_related(
                    'academic_session', 'academic_term', 'class_obj', 'class_arm'
                ).order_by('-academic_session__start_date')
            ),
            Prefetch(
                'guardians',
                queryset=StudentGuardian.objects.select_related('guardian')
            ),
        )
        .get(user=user)
    )


def build_parent_self_profile_payload(user) -> dict:
    """
    Constructs the /api/v1/profile/parent/ payload for an authenticated parent/guardian,
    listing their account info and all linked children via StudentGuardian.
    """
    settings_obj = SchoolSettings.load()
    guardian_links = (
        StudentGuardian.objects.filter(guardian=user)
        .select_related('student__user')
        .order_by('student__last_name', 'student__first_name')
    )

    children_data = []
    for link in guardian_links:
        student = link.student
        enrollment = (
            StudentEnrollment.objects.filter(
                student=student,
                academic_session=settings_obj.current_session
            )
            .select_related('academic_session', 'class_obj', 'class_arm')
            .first()
        ) or (
            StudentEnrollment.objects.filter(student=student)
            .select_related('academic_session', 'class_obj', 'class_arm')
            .order_by('-created_at')
            .first()
        )

        children_data.append({
            "guardian_link_id": str(link.id),
            "relationship": link.relationship,
            "is_primary_guardian": getattr(link, 'is_primary', False),
            "student_id": str(student.id),
            "admission_number": student.user.login_id if student.user else None,
            "first_name": student.first_name,
            "middle_name": student.middle_name,
            "last_name": student.last_name,
            "full_name": f"{student.last_name}, {student.first_name} {student.middle_name or ''}".strip(),
            "gender": student.gender,
            "date_of_birth": str(student.date_of_birth) if student.date_of_birth else None,
            "current_enrollment": {
                "enrollment_id": str(enrollment.id),
                "session": enrollment.academic_session.name,
                "class_name": enrollment.class_obj.name,
                "class_arm": enrollment.class_arm.name if enrollment.class_arm else None,
                "status": enrollment.status,
            } if enrollment else None,
        })

    return {
        "guardian": {
            "id": str(user.id),
            "login_id": user.login_id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "full_name": f"{user.first_name} {user.last_name}".strip(),
            "phone_number": getattr(user, 'phone_number', None),
        },
        "linked_children_count": len(children_data),
        "linked_children": children_data,
    }