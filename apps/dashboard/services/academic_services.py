from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Avg, Count, Max, Min, Q, Prefetch

from apps.academics.models import AcademicSession, AcademicTerm, Class, ClassArm, ClassSubject, SchoolSettings, Subject
from apps.dashboard.services.dashboard_services import get_parent_guardian_links_queryset
from apps.examinations.models import ResultWorkflowStatus, StudentResult, StudentTermSummary
from apps.staff.models import Department, Designation, Staff, StaffEmployment, TeacherAssignment
from apps.students.models import StudentEnrollment




def build_academic_overview_payload(user, session_id=None) -> dict:
    """
    Constructs the /api/v1/dashboard/academic-overview/ payload.
    Reuses Phase 3 models (AcademicSession, AcademicTerm, Class, ClassArm, Subject, ClassSubject)
    and scopes class/subject visibility according to the authenticated user's role.
    """
    settings_obj = SchoolSettings.load()
    role_names = set(user.roles.values_list('name', flat=True))
    is_admin = user.is_superuser or bool(role_names.intersection({'SUPER_ADMIN', 'ADMIN'}))
    is_staff = 'STAFF' in role_names and hasattr(user, 'staff_profile') and user.staff_profile is not None
    is_student = 'STUDENT' in role_names and hasattr(user, 'student_profile') and user.student_profile is not None
    is_parent = 'PARENT' in role_names or get_parent_guardian_links_queryset(user).exists()

    # 1. Resolve Target & Available Sessions / Terms
    sessions_qs = AcademicSession.objects.prefetch_related(
        Prefetch('terms', queryset=AcademicTerm.objects.order_by('start_date'))
    ).order_by('-start_date')

    if session_id:
        target_session = AcademicSession.objects.filter(pk=session_id).first()
    else:
        target_session = settings_obj.current_session or sessions_qs.first()

    current_term = settings_obj.current_term
    if target_session and (not current_term or current_term.session_id != target_session.id):
        current_term = AcademicTerm.objects.filter(session=target_session).order_by('start_date').first()

    available_sessions = []
    for s in sessions_qs:
        available_sessions.append({
            "id": str(s.id),
            "name": s.name,
            "start_date": str(s.start_date),
            "end_date": str(s.end_date),
            "is_current": bool(settings_obj.current_session_id == s.id),
            "terms": [
                {
                    "id": str(t.id),
                    "name": t.name,
                    "display_name": t.get_name_display(),
                    "start_date": str(t.start_date),
                    "end_date": str(t.end_date),
                    "is_current": bool(settings_obj.current_term_id == t.id),
                }
                for t in s.terms.all()
            ],
        })

    # 2. Determine Class Scope Based on User Role
    allowed_class_ids = None  # None means full visibility (Admin / Staff)
    staff_assigned_class_ids = set()
    staff_assigned_subject_ids = set()

    if is_admin:
        allowed_class_ids = None
    elif is_staff:
        allowed_class_ids = None
        if target_session:
            ta_qs = TeacherAssignment.objects.filter(
                staff=user.staff_profile,
                academic_session=target_session,
                is_active=True,
            )
            for ta in ta_qs:
                staff_assigned_class_ids.add(ta.class_obj_id)
                if ta.subject_id:
                    staff_assigned_subject_ids.add(ta.subject_id)
    elif is_student or is_parent:
        scoped_ids = set()
        if is_student:
            st_enr_qs = StudentEnrollment.objects.filter(student=user.student_profile)
            if target_session:
                st_enr_qs = st_enr_qs.filter(academic_session=target_session)
            scoped_ids.update(st_enr_qs.values_list('class_obj_id', flat=True))

        if is_parent:
            child_ids = get_parent_guardian_links_queryset(user).values_list('student_id', flat=True)
            pr_enr_qs = StudentEnrollment.objects.filter(student_id__in=child_ids)
            if target_session:
                pr_enr_qs = pr_enr_qs.filter(academic_session=target_session)
            scoped_ids.update(pr_enr_qs.values_list('class_obj_id', flat=True))

        allowed_class_ids = scoped_ids

    # 3. Fetch Classes & Class Arms
    classes_qs = Class.objects.all()
    if hasattr(Class, 'is_active'):
        classes_qs = classes_qs.filter(is_active=True)
    if allowed_class_ids is not None:
        classes_qs = classes_qs.filter(id__in=allowed_class_ids)

    arms_qs = ClassArm.objects.select_related('class_obj').order_by('name')
    if hasattr(ClassArm, 'is_active'):
        arms_qs = arms_qs.filter(is_active=True)

    classes_qs = classes_qs.prefetch_related(
        Prefetch('arms' if hasattr(Class, 'arms') else 'classarm_set', queryset=arms_qs, to_attr='prefetched_arms')
    ).order_by('display_order' if hasattr(Class, 'display_order') else 'name')

    classes_list = []
    class_arms_list = []
    for cls in classes_qs:
        cls_arms = getattr(cls, 'prefetched_arms', [])
        classes_list.append({
            "id": str(cls.id),
            "name": cls.name,
            "code": getattr(cls, 'code', None),
            "education_level": getattr(cls, 'education_level', None),
            "display_order": getattr(cls, 'display_order', None),
            "is_assigned_to_me": cls.id in staff_assigned_class_ids if is_staff else None,
            "arms": [
                {
                    "id": str(arm.id),
                    "name": arm.name,
                }
                for arm in cls_arms
            ],
        })
        for arm in cls_arms:
            class_arms_list.append({
                "id": str(arm.id),
                "name": arm.name,
                "class_id": str(cls.id),
                "class_name": cls.name,
                "label": f"{cls.name} - {arm.name}",
            })

    # 4. Fetch Class-Subject Relationships & Subjects
    class_subjects_qs = (
        ClassSubject.objects.filter(is_active=True)
        .select_related('class_obj', 'subject')
        .order_by('class_obj__name', 'subject__name')
    )
    if allowed_class_ids is not None:
        class_subjects_qs = class_subjects_qs.filter(class_obj_id__in=allowed_class_ids)

    class_subject_mappings = []
    visible_subject_ids = set()
    for cs in class_subjects_qs:
        visible_subject_ids.add(cs.subject_id)
        class_subject_mappings.append({
            "id": str(cs.id),
            "class_id": str(cs.class_obj_id),
            "class_name": cs.class_obj.name,
            "subject_id": str(cs.subject_id),
            "subject_name": cs.subject.name,
            "subject_code": cs.subject.code,
            "is_compulsory": getattr(cs, 'is_compulsory', getattr(cs.subject, 'is_compulsory', True)),
        })

    subjects_qs = Subject.objects.all()
    if hasattr(Subject, 'is_active'):
        subjects_qs = subjects_qs.filter(is_active=True)
    if allowed_class_ids is not None:
        subjects_qs = subjects_qs.filter(id__in=visible_subject_ids)
    subjects_qs = subjects_qs.order_by('name')

    subjects_list = [
        {
            "id": str(subj.id),
            "name": subj.name,
            "code": subj.code,
            "department": getattr(subj, 'department', None),
            "is_compulsory": getattr(subj, 'is_compulsory', True),
            "is_assigned_to_me": subj.id in staff_assigned_subject_ids if is_staff else None,
        }
        for subj in subjects_qs
    ]

    return {
        "school_context": {
            "school_name": getattr(settings_obj, 'school_name', 'Almawrid Islamic International College'),
            "school_motto": getattr(settings_obj, 'school_motto', ''),
            "current_session": {
                "id": str(target_session.id),
                "name": target_session.name,
                "start_date": str(target_session.start_date),
                "end_date": str(target_session.end_date),
            } if target_session else None,
            "current_term": {
                "id": str(current_term.id),
                "name": current_term.name,
                "display_name": current_term.get_name_display(),
                "start_date": str(current_term.start_date),
                "end_date": str(current_term.end_date),
            } if current_term else None,
        },
        "available_sessions": available_sessions,
        "classes": classes_list,
        "class_arms": class_arms_list,
        "subjects": subjects_list,
        "class_subjects": class_subject_mappings,
    }


def build_enrollment_analytics_payload(session_id=None) -> dict:
    """
    Constructs deep enrollment statistics for /api/v1/dashboard/analytics/enrollments/.
    Uses single-pass conditional ORM aggregations across StudentEnrollment.
    """
    settings_obj = SchoolSettings.load()
    if session_id:
        target_session = AcademicSession.objects.filter(pk=session_id).first()
    else:
        target_session = settings_obj.current_session or AcademicSession.objects.order_by('-start_date').first()

    qs = StudentEnrollment.objects.all()
    if target_session:
        qs = qs.filter(academic_session=target_session)

    summary = qs.aggregate(
        total_enrollments=Count('id'),
        enrolled_active=Count('id', filter=Q(status='ENROLLED')),
        completed=Count('id', filter=Q(status='COMPLETED')),
        graduated=Count('id', filter=Q(status='GRADUATED')),
        withdrawn=Count('id', filter=Q(status='WITHDRAWN')),
        male_enrolled=Count('id', filter=Q(status='ENROLLED', student__gender__iexact='MALE')),
        female_enrolled=Count('id', filter=Q(status='ENROLLED', student__gender__iexact='FEMALE')),
    )

    # Breakdown by Education Level (active enrollments)
    level_rows = (
        qs.filter(status='ENROLLED')
        .values('class_obj__education_level')
        .annotate(
            total=Count('id'),
            male=Count('id', filter=Q(student__gender__iexact='MALE')),
            female=Count('id', filter=Q(student__gender__iexact='FEMALE')),
        )
        .order_by('class_obj__education_level')
    )
    by_education_level = [
        {
            "education_level": row['class_obj__education_level'],
            "total_students": row['total'],
            "male_students": row['male'],
            "female_students": row['female'],
        }
        for row in level_rows
    ]

    # Breakdown by Class (all statuses + gender for active)
    class_rows = (
        qs.values('class_obj__id', 'class_obj__name', 'class_obj__education_level')
        .annotate(
            enrolled=Count('id', filter=Q(status='ENROLLED')),
            male=Count('id', filter=Q(status='ENROLLED', student__gender__iexact='MALE')),
            female=Count('id', filter=Q(status='ENROLLED', student__gender__iexact='FEMALE')),
            withdrawn=Count('id', filter=Q(status='WITHDRAWN')),
            graduated=Count('id', filter=Q(status='GRADUATED')),
        )
        .order_by('class_obj__name')
    )
    by_class = [
        {
            "class_id": str(r['class_obj__id']),
            "class_name": r['class_obj__name'],
            "education_level": r['class_obj__education_level'],
            "enrolled_count": r['enrolled'],
            "male_count": r['male'],
            "female_count": r['female'],
            "withdrawn_count": r['withdrawn'],
            "graduated_count": r['graduated'],
        }
        for r in class_rows
    ]

    # Breakdown by Class Arm
    arm_rows = (
        qs.filter(status='ENROLLED', class_arm__isnull=False)
        .values('class_obj__id', 'class_obj__name', 'class_arm__id', 'class_arm__name')
        .annotate(
            total=Count('id'),
            male=Count('id', filter=Q(student__gender__iexact='MALE')),
            female=Count('id', filter=Q(student__gender__iexact='FEMALE')),
        )
        .order_by('class_obj__name', 'class_arm__name')
    )
    by_class_arm = [
        {
            "class_id": str(r['class_obj__id']),
            "class_name": r['class_obj__name'],
            "class_arm_id": str(r['class_arm__id']),
            "class_arm_name": r['class_arm__name'],
            "label": f"{r['class_obj__name']} - {r['class_arm__name']}",
            "total_students": r['total'],
            "male_count": r['male'],
            "female_count": r['female'],
        }
        for r in arm_rows
    ]

    # Historical Trend Across Academic Sessions
    session_trend_rows = (
        StudentEnrollment.objects.values(
            'academic_session__id',
            'academic_session__name',
            'academic_session__start_date',
        )
        .annotate(
            total_enrollments=Count('id'),
            active_enrolled=Count('id', filter=Q(status='ENROLLED')),
            graduated=Count('id', filter=Q(status='GRADUATED')),
        )
        .order_by('academic_session__start_date')
    )
    session_trends = [
        {
            "session_id": str(r['academic_session__id']),
            "session_name": r['academic_session__name'],
            "total_enrollments": r['total_enrollments'],
            "active_enrolled": r['active_enrolled'],
            "graduated": r['graduated'],
        }
        for r in session_trend_rows
    ]

    return {
        "session_context": {
            "id": str(target_session.id),
            "name": target_session.name,
        } if target_session else None,
        "summary": summary,
        "by_education_level": by_education_level,
        "by_class": by_class,
        "by_class_arm": by_class_arm,
        "historical_session_trends": session_trends,
    }


def build_staff_analytics_payload(session_id=None) -> dict:
    """
    Constructs deep staff & HR analytics for /api/v1/dashboard/analytics/staff/.
    """
    settings_obj = SchoolSettings.load()
    target_session = (
        AcademicSession.objects.filter(pk=session_id).first()
        if session_id
        else (settings_obj.current_session or AcademicSession.objects.order_by('-start_date').first())
    )

    staff_demographics = Staff.objects.aggregate(
        total_staff_profiles=Count('id'),
        male_staff=Count('id', filter=Q(gender__iexact='MALE')),
        female_staff=Count('id', filter=Q(gender__iexact='FEMALE')),
    )

    employment_summary = StaffEmployment.objects.aggregate(
        active=Count('staff_id', filter=Q(status=StaffEmployment.EmploymentStatus.ACTIVE), distinct=True),
        on_leave=Count('staff_id', filter=Q(status=StaffEmployment.EmploymentStatus.ON_LEAVE), distinct=True),
        suspended=Count('staff_id', filter=Q(status=StaffEmployment.EmploymentStatus.SUSPENDED), distinct=True),
        resigned=Count('staff_id', filter=Q(status=StaffEmployment.EmploymentStatus.RESIGNED), distinct=True),
        terminated=Count('staff_id', filter=Q(status=StaffEmployment.EmploymentStatus.TERMINATED), distinct=True),
        retired=Count('staff_id', filter=Q(status=StaffEmployment.EmploymentStatus.RETIRED), distinct=True),
    )

    active_emp_qs = StaffEmployment.objects.filter(status=StaffEmployment.EmploymentStatus.ACTIVE)

    by_employment_type = [
        {
            "employment_type": r['employment_type'],
            "staff_count": r['count'],
        }
        for r in active_emp_qs.values('employment_type').annotate(count=Count('staff_id', distinct=True)).order_by('employment_type')
    ]

    by_category = [
        {
            "category": r['designation__category'],
            "staff_count": r['count'],
        }
        for r in active_emp_qs.values('designation__category').annotate(count=Count('staff_id', distinct=True)).order_by('designation__category')
    ]

    by_department = [
        {
            "department_id": str(d.id),
            "name": d.name,
            "code": d.code,
            "head_name": str(d.head) if d.head else None,
            "active_staff_count": d.active_count,
            "male_count": d.male_count,
            "female_count": d.female_count,
        }
        for d in Department.objects.filter(is_active=True)
        .select_related('head')
        .annotate(
            active_count=Count(
                'staff_members__staff_id',
                filter=Q(staff_members__status=StaffEmployment.EmploymentStatus.ACTIVE),
                distinct=True,
            ),
            male_count=Count(
                'staff_members__staff_id',
                filter=Q(
                    staff_members__status=StaffEmployment.EmploymentStatus.ACTIVE,
                    staff_members__staff__gender__iexact='MALE',
                ),
                distinct=True,
            ),
            female_count=Count(
                'staff_members__staff_id',
                filter=Q(
                    staff_members__status=StaffEmployment.EmploymentStatus.ACTIVE,
                    staff_members__staff__gender__iexact='FEMALE',
                ),
                distinct=True,
            ),
        )
        .order_by('name')
    ]

    by_designation = [
        {
            "designation_id": str(des.id),
            "name": des.name,
            "code": des.code,
            "category": des.category,
            "active_staff_count": des.active_count,
        }
        for des in Designation.objects.filter(is_active=True)
        .annotate(
            active_count=Count(
                'staff_members__staff_id',
                filter=Q(staff_members__status=StaffEmployment.EmploymentStatus.ACTIVE),
                distinct=True,
            )
        )
        .order_by('category', 'name')
    ]

    teaching_workload = {
        "session": target_session.name if target_session else None,
        "total_active_assignments": 0,
        "unique_assigned_teachers": 0,
        "class_teachers_count": 0,
        "subject_teachers_count": 0,
    }
    if target_session:
        ta_stats = TeacherAssignment.objects.filter(
            academic_session=target_session,
            is_active=True,
        ).aggregate(
            total_active_assignments=Count('id'),
            unique_assigned_teachers=Count('staff_id', distinct=True),
            class_teachers_count=Count(
                'staff_id',
                filter=Q(is_class_teacher=True) | Q(assignment_type=TeacherAssignment.AssignmentType.CLASS_TEACHER),
                distinct=True,
            ),
            subject_teachers_count=Count(
                'staff_id',
                filter=Q(assignment_type=TeacherAssignment.AssignmentType.SUBJECT_TEACHER),
                distinct=True,
            ),
        )
        teaching_workload.update(ta_stats)

    return {
        "demographics": staff_demographics,
        "employment_status_breakdown": employment_summary,
        "active_by_employment_type": by_employment_type,
        "active_by_category": by_category,
        "by_department": by_department,
        "by_designation": by_designation,
        "teaching_workload_summary": teaching_workload,
    }


def build_result_analytics_payload(session_id=None, term_id=None, class_id=None) -> dict:
    """
    Constructs deep examination and result analytics for /api/v1/dashboard/analytics/results/.
    Computes workflow pipeline counts, class performance comparisons, subject pass rates,
    and school-wide grade distributions (A-F) using single-pass ORM aggregations.
    """
    settings_obj = SchoolSettings.load()
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

    summaries_qs = StudentTermSummary.objects.all()
    results_qs = StudentResult.objects.all()

    if target_term:
        summaries_qs = summaries_qs.filter(academic_term=target_term)
        results_qs = results_qs.filter(academic_term=target_term)
    elif target_session:
        summaries_qs = summaries_qs.filter(student_enrollment__academic_session=target_session)
        results_qs = results_qs.filter(student_enrollment__academic_session=target_session)

    if class_id:
        summaries_qs = summaries_qs.filter(student_enrollment__class_obj_id=class_id)
        results_qs = results_qs.filter(student_enrollment__class_obj_id=class_id)

    # 1. Workflow Pipeline & Overall Term KPIs
    overall_agg = summaries_qs.aggregate(
        total_summaries=Count('id'),
        draft=Count('id', filter=Q(status=ResultWorkflowStatus.DRAFT)),
        scores_submitted=Count('id', filter=Q(status=ResultWorkflowStatus.SCORES_SUBMITTED)),
        under_review=Count('id', filter=Q(status=ResultWorkflowStatus.UNDER_REVIEW)),
        approved=Count('id', filter=Q(status=ResultWorkflowStatus.APPROVED)),
        published=Count('id', filter=Q(status=ResultWorkflowStatus.PUBLISHED)),
        locked=Count('id', filter=Q(status=ResultWorkflowStatus.LOCKED)),
        mean_average=Avg('average_score'),
        mean_gpa=Avg('gpa'),
        highest_average=Max('average_score'),
        lowest_average=Min('average_score'),
        students_passing_overall=Count('id', filter=Q(average_score__gte=Decimal('40.00'))),
    )

    total_sum_count = overall_agg['total_summaries'] or 0
    overall_pass_rate = (
        (Decimal(overall_agg['students_passing_overall']) / Decimal(total_sum_count) * Decimal('100.00')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        if total_sum_count > 0
        else Decimal('0.00')
    )

    # 2. Class-by-Class Performance Comparison
    class_perf_rows = (
        summaries_qs.values(
            'student_enrollment__class_obj__id',
            'student_enrollment__class_obj__name',
        )
        .annotate(
            student_count=Count('id'),
            class_mean_average=Avg('average_score'),
            class_mean_gpa=Avg('gpa'),
            highest_average=Max('average_score'),
            lowest_average=Min('average_score'),
            passed_count=Count('id', filter=Q(average_score__gte=Decimal('40.00'))),
            published_count=Count(
                'id',
                filter=Q(status__in=[ResultWorkflowStatus.PUBLISHED, ResultWorkflowStatus.LOCKED]),
            ),
        )
        .order_by('student_enrollment__class_obj__name')
    )

    class_performance = []
    for row in class_perf_rows:
        s_cnt = row['student_count'] or 0
        p_rate = (
            (Decimal(row['passed_count']) / Decimal(s_cnt) * Decimal('100.00')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            if s_cnt > 0
            else Decimal('0.00')
        )
        class_performance.append({
            "class_id": str(row['student_enrollment__class_obj__id']),
            "class_name": row['student_enrollment__class_obj__name'],
            "student_count": s_cnt,
            "mean_average": str((row['class_mean_average'] or Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            "mean_gpa": str((row['class_mean_gpa'] or Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            "highest_average": str((row['highest_average'] or Decimal('0.00')).quantize(Decimal('0.01'))),
            "lowest_average": str((row['lowest_average'] or Decimal('0.00')).quantize(Decimal('0.01'))),
            "passed_count": row['passed_count'],
            "pass_rate_percentage": str(p_rate),
            "published_count": row['published_count'],
        })

    # 3. Grade Distribution (A, B, C, D, E, F) across Subject Results
    grade_rows = (
        results_qs.values('grade')
        .annotate(count=Count('id'))
        .order_by('grade')
    )
    total_subject_results = sum(r['count'] for r in grade_rows)
    grade_distribution = []
    for r in grade_rows:
        g_cnt = r['count']
        pct = (
            (Decimal(g_cnt) / Decimal(total_subject_results) * Decimal('100.00')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            if total_subject_results > 0
            else Decimal('0.00')
        )
        grade_distribution.append({
            "grade": r['grade'] or "UNGRADED",
            "count": g_cnt,
            "percentage": str(pct),
        })

    # 4. Subject Performance Summary
    subject_rows = (
        results_qs.values('subject__id', 'subject__name', 'subject__code')
        .annotate(
            entries_count=Count('id'),
            mean_score=Avg('total_score'),
            highest_score=Max('total_score'),
            lowest_score=Min('total_score'),
            passed_count=Count('id', filter=Q(total_score__gte=Decimal('40.00'))),
        )
        .order_by('subject__name')
    )
    subject_performance = []
    for r in subject_rows:
        e_cnt = r['entries_count'] or 0
        s_pass_rate = (
            (Decimal(r['passed_count']) / Decimal(e_cnt) * Decimal('100.00')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            if e_cnt > 0
            else Decimal('0.00')
        )
        subject_performance.append({
            "subject_id": str(r['subject__id']),
            "subject_name": r['subject__name'],
            "subject_code": r['subject__code'],
            "entries_count": e_cnt,
            "mean_score": str((r['mean_score'] or Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            "highest_score": str((r['highest_score'] or Decimal('0.00')).quantize(Decimal('0.01'))),
            "lowest_score": str((r['lowest_score'] or Decimal('0.00')).quantize(Decimal('0.01'))),
            "passed_count": r['passed_count'],
            "pass_rate_percentage": str(s_pass_rate),
        })

    return {
        "academic_context": {
            "session": {
                "id": str(target_session.id),
                "name": target_session.name,
            } if target_session else None,
            "term": {
                "id": str(target_term.id),
                "name": target_term.name,
                "display_name": target_term.get_name_display(),
            } if target_term else None,
            "filtered_class_id": str(class_id) if class_id else None,
        },
        "workflow_pipeline": {
            "total_summaries": total_sum_count,
            "draft": overall_agg['draft'],
            "scores_submitted": overall_agg['scores_submitted'],
            "under_review": overall_agg['under_review'],
            "approved": overall_agg['approved'],
            "published": overall_agg['published'],
            "locked": overall_agg['locked'],
        },
        "overall_performance": {
            "total_evaluated_students": total_sum_count,
            "mean_average": str((overall_agg['mean_average'] or Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            "mean_gpa": str((overall_agg['mean_gpa'] or Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            "highest_average": str((overall_agg['highest_average'] or Decimal('0.00')).quantize(Decimal('0.01'))),
            "lowest_average": str((overall_agg['lowest_average'] or Decimal('0.00')).quantize(Decimal('0.01'))),
            "students_passing_overall": overall_agg['students_passing_overall'],
            "overall_pass_rate_percentage": str(overall_pass_rate),
        },
        "class_performance_comparison": class_performance,
        "grade_distribution": grade_distribution,
        "subject_performance_summary": subject_performance,
    }