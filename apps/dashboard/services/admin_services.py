from django.db.models import Q, Prefetch
from django.db.models.aggregates import Count

from apps.academics.models import (
    AcademicSession, 
    AcademicTerm, 
    Class, 
    ClassArm, 
    SchoolSettings, 
    Subject
)

from apps.examinations.models import (
    Examination, 
    ResultWorkflowAudit, 
    ResultWorkflowStatus, 
    StudentTermSummary
)

from apps.staff.models import (
    Department, 
    Designation, 
    Staff, 
    StaffEmployment
)

from apps.students.models import Student, StudentEnrollment



def build_admin_dashboard_payload(session_id=None, term_id=None) -> dict:
    """
    Aggregates school-wide KPIs, enrollment distributions, department staff counts,
    result workflow states, and recent onboarding records for the Administrator Dashboard.
    Uses single-pass conditional Count aggregations to avoid N+1 queries.
    """
    settings_obj = SchoolSettings.load()

    # 1. Resolve target Academic Session & Term (defaults to active SchoolSettings)
    if session_id:
        target_session = AcademicSession.objects.filter(pk=session_id).first()
    else:
        target_session = settings_obj.current_session or AcademicSession.objects.order_by('-start_date').first()

    if term_id:
        target_term = AcademicTerm.objects.filter(pk=term_id).first()
    elif settings_obj.current_term and target_session and settings_obj.current_term.session_id == target_session.id:
        target_term = settings_obj.current_term
    elif target_session:
        target_term = AcademicTerm.objects.filter(session=target_session).order_by('start_date').first()
    else:
        target_term = None

    # 2. Student KPIs (Global & Current Session Enrollment breakdown)
    student_global_stats = Student.objects.aggregate(
        total_registered=Count('id'),
        male_students=Count('id', filter=Q(gender__iexact='MALE')),
        female_students=Count('id', filter=Q(gender__iexact='FEMALE')),
    )

    enrollment_qs = StudentEnrollment.objects.all()
    if target_session:
        enrollment_qs = enrollment_qs.filter(academic_session=target_session)

    enrollment_stats = enrollment_qs.aggregate(
        active_enrolled=Count('id', filter=Q(status='ENROLLED')),
        completed_session=Count('id', filter=Q(status='COMPLETED')),
        graduated=Count('id', filter=Q(status='GRADUATED')),
        withdrawn=Count('id', filter=Q(status='WITHDRAWN')),
    )

    #Also include total historical graduated students across all sessions
    total_graduated_all_time = (
        StudentEnrollment.objects.filter(status='GRADUATED')
        .values('student_id')
        .distinct()
        .count()
    )

    # 3. Staff KPIs (Single-pass aggregation across Staff & StaffEmployment)
    total_staff_count = Staff.objects.count()
    active_employment_qs = StaffEmployment.objects.filter(
        status=StaffEmployment.EmploymentStatus.ACTIVE
    )
    staff_emp_stats = active_employment_qs.aggregate(
        active_staff=Count('staff_id', distinct=True),
        teaching_staff=Count(
            'staff_id',
            filter=Q(designation__category=Designation.Category.ACADEMIC),
            distinct=True,
        ),
        administrative_staff=Count(
            'staff_id',
            filter=Q(designation__category=Designation.Category.ADMINISTRATIVE),
            distinct=True,
        ),
        technical_and_support_staff=Count(
            'staff_id',
            filter=Q(designation__category__in=[Designation.Category.TECHNICAL, Designation.Category.SUPPORT]),
            distinct=True,
        ),
    )

    # 4. Academic Structure KPIs
    academics_summary = {
        "total_classes": Class.objects.filter(is_active=True).count() if hasattr(Class, 'is_active') else Class.objects.count(),
        "total_class_arms": ClassArm.objects.filter(is_active=True).count() if hasattr(ClassArm, 'is_active') else ClassArm.objects.count(),
        "total_subjects": Subject.objects.filter(is_active=True).count() if hasattr(Subject, 'is_active') else Subject.objects.count(),
        "total_departments": Department.objects.filter(is_active=True).count(),
    }

    # 5. Student Enrollment Distribution by Class (for target session)
    class_distribution = []
    if target_session:
        class_rows = (
            StudentEnrollment.objects.filter(
                academic_session=target_session,
                status='ENROLLED',
            )
            .values(
                'class_obj__id',
                'class_obj__name',
                'class_obj__education_level',
            )
            .annotate(
                total_students=Count('id'),
                male_count=Count('id', filter=Q(student__gender__iexact='MALE')),
                female_count=Count('id', filter=Q(student__gender__iexact='FEMALE')),
            )
            .order_by('class_obj__name')
        )
        for row in class_rows:
            class_distribution.append({
                "class_id": str(row['class_obj__id']),
                "class_name": row['class_obj__name'],
                "education_level": row['class_obj__education_level'],
                "total_students": row['total_students'],
                "male_count": row['male_count'],
                "female_count": row['female_count'],
            })

    # 6. Student Distribution by Class Arm (for target session)
    arm_distribution = []
    if target_session:
        arm_rows = (
            StudentEnrollment.objects.filter(
                academic_session=target_session,
                status='ENROLLED',
                class_arm__isnull=False,
            )
            .values(
                'class_obj__id',
                'class_obj__name',
                'class_arm__id',
                'class_arm__name',
            )
            .annotate(total_students=Count('id'))
            .order_by('class_obj__name', 'class_arm__name')
        )
        for row in arm_rows:
            arm_distribution.append({
                "class_id": str(row['class_obj__id']),
                "class_name": row['class_obj__name'],
                "class_arm_id": str(row['class_arm__id']),
                "class_arm_name": row['class_arm__name'],
                "label": f"{row['class_obj__name']} - {row['class_arm__name']}",
                "total_students": row['total_students'],
            })

    # 7. Staff Distribution by Department (Active employment records)
    department_rows = (
        Department.objects.filter(is_active=True)
        .select_related('head')
        .annotate(
            active_staff_count=Count(
                'staff_members__staff_id',
                filter=Q(staff_members__status=StaffEmployment.EmploymentStatus.ACTIVE),
                distinct=True,
            )
        )
        .order_by('name')
    )
    staff_by_department = [
        {
            "department_id": str(dept.id),
            "name": dept.name,
            "code": dept.code,
            "head_name": str(dept.head) if dept.head else None,
            "active_staff_count": dept.active_staff_count,
        }
        for dept in department_rows
    ]

    # 8. Examinations & Result Workflow Snapshot (for target term)
    results_overview = {
        "active_examinations_count": 0,
        "workflow_breakdown": {
            "draft": 0,
            "scores_submitted": 0,
            "under_review": 0,
            "approved": 0,
            "published": 0,
            "locked": 0,
        },
        "recent_workflow_audits": [],
    }

    if target_term:
        results_overview["active_examinations_count"] = Examination.objects.filter(
            academic_term=target_term,
            is_active=True,
        ).count()

        wf_stats = StudentTermSummary.objects.filter(academic_term=target_term).aggregate(
            draft=Count('id', filter=Q(status=ResultWorkflowStatus.DRAFT)),
            scores_submitted=Count('id', filter=Q(status=ResultWorkflowStatus.SCORES_SUBMITTED)),
            under_review=Count('id', filter=Q(status=ResultWorkflowStatus.UNDER_REVIEW)),
            approved=Count('id', filter=Q(status=ResultWorkflowStatus.APPROVED)),
            published=Count('id', filter=Q(status=ResultWorkflowStatus.PUBLISHED)),
            locked=Count('id', filter=Q(status=ResultWorkflowStatus.LOCKED)),
        )
        results_overview["workflow_breakdown"] = wf_stats

        recent_audits = (
            ResultWorkflowAudit.objects.filter(academic_term=target_term)
            .select_related('class_obj', 'class_arm', 'subject', 'performed_by')
            .order_by('-created_at')[:8]
        )
        results_overview["recent_workflow_audits"] = [
            {
                "id": str(audit.id),
                "class_name": audit.class_obj.name,
                "class_arm": audit.class_arm.name if audit.class_arm else None,
                "subject": audit.subject.name if audit.subject else None,
                "previous_status": audit.previous_status,
                "new_status": audit.new_status,
                "performed_by": f"{audit.performed_by.first_name} {audit.performed_by.last_name}".strip() if audit.performed_by else "System",
                "reason": audit.reason,
                "timestamp": audit.created_at.isoformat(),
            }
            for audit in recent_audits
        ]

    # 9. Recent Student Admissions (Last 5)
    recent_students_qs = (
        Student.objects.select_related('user')
        .prefetch_related(
            Prefetch(
                'enrollments',
                queryset=StudentEnrollment.objects.select_related('class_obj', 'class_arm', 'academic_session').order_by('-created_at'),
            )
        )
        .order_by('-created_at')[:5]
    )
    recent_admissions = []
    for st in recent_students_qs:
        latest_enr = st.enrollments.all()[0] if st.enrollments.all() else None
        recent_admissions.append({
            "student_id": str(st.id),
            "admission_number": st.user.login_id if st.user else None,
            "full_name": f"{st.last_name}, {st.first_name} {st.middle_name or ''}".strip(),
            "gender": st.gender,
            "class_name": latest_enr.class_obj.name if latest_enr else None,
            "class_arm": latest_enr.class_arm.name if (latest_enr and latest_enr.class_arm) else None,
            "session": latest_enr.academic_session.name if latest_enr else None,
            "admitted_at": st.created_at.isoformat(),
        })

    # 10. Recent Staff Registrations (Last 5)
    recent_staff_qs = (
        Staff.objects.select_related('user')
        .prefetch_related(
            Prefetch(
                'employment_records',
                queryset=StaffEmployment.objects.select_related('department', 'designation').order_by('-start_date'),
            )
        )
        .order_by('-created_at')[:5]
    )
    recent_staff = []
    for sf in recent_staff_qs:
        latest_emp = sf.employment_records.all()[0] if sf.employment_records.all() else None
        recent_staff.append({
            "staff_profile_id": str(sf.id),
            "staff_id": sf.user.login_id if sf.user else None,
            "full_name": f"{sf.last_name}, {sf.first_name} {sf.middle_name or ''}".strip(),
            "gender": sf.gender,
            "department": latest_emp.department.name if latest_emp else None,
            "designation": latest_emp.designation.name if latest_emp else None,
            "status": latest_emp.status if latest_emp else None,
            "registered_at": sf.created_at.isoformat(),
        })

    return {
        "school_context": {
            "school_name": getattr(settings_obj, 'school_name', 'Almawrid Islamic International College'),
            "school_motto": getattr(settings_obj, 'school_motto', ''),
            "active_session": {
                "id": str(target_session.id),
                "name": target_session.name,
                "start_date": str(target_session.start_date),
                "end_date": str(target_session.end_date),
            } if target_session else None,
            "active_term": {
                "id": str(target_term.id),
                "name": target_term.name,
                "display_name": target_term.get_name_display(),
                "start_date": str(target_term.start_date),
                "end_date": str(target_term.end_date),
            } if target_term else None,
        },
        "kpis": {
            "students": {
                "total_registered": student_global_stats['total_registered'],
                "male_students": student_global_stats['male_students'],
                "female_students": student_global_stats['female_students'],
                "active_in_session": enrollment_stats['active_enrolled'],
                "completed_in_session": enrollment_stats['completed_session'],
                "graduated_in_session": enrollment_stats['graduated'],
                "withdrawn_in_session": enrollment_stats['withdrawn'],
                "total_graduated_all_time": total_graduated_all_time,
            },
            "staff": {
                "total_registered": total_staff_count,
                "active_staff": staff_emp_stats['active_staff'],
                "teaching_staff": staff_emp_stats['teaching_staff'],
                "administrative_staff": staff_emp_stats['administrative_staff'],
                "technical_and_support_staff": staff_emp_stats['technical_and_support_staff'],
            },
            "academics": academics_summary,
        },
        "distributions": {
            "enrollments_by_class": class_distribution,
            "enrollments_by_class_arm": arm_distribution,
            "staff_by_department": staff_by_department,
        },
        "examinations_and_results": results_overview,
        "recent_activity": {
            "recent_student_admissions": recent_admissions,
            "recent_staff_registrations": recent_staff,
        },
    }
