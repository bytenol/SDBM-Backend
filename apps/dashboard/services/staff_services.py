from django.db.models import Q
from django.db.models.aggregates import Count

from apps.academics.models import AcademicSession, AcademicTerm, SchoolSettings
from apps.examinations.models import (
    Examination,
    StudentScore,
    ResultWorkflowAudit,
)
from apps.staff.models import Designation, Staff, StaffEmployment, TeacherAssignment
from apps.students.models import StudentEnrollment



def build_staff_dashboard_payload(user, session_id=None, term_id=None) -> dict:
    """
    Constructs the Staff Dashboard payload for the authenticated staff member.
    Gracefully handles both teaching staff (with TeacherAssignment records) and
    non-teaching staff (administrative, technical, and support personnel).
    """
    settings_obj = SchoolSettings.load()
    staff = (
        Staff.objects.select_related('user')
        .prefetch_related('headed_departments', 'qualifications')
        .get(user=user)
    )

    # 1. Resolve target Academic Session & Term
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

    # 2. Active Employment & Department Context
    active_employment = (
        StaffEmployment.objects.filter(staff=staff, status=StaffEmployment.EmploymentStatus.ACTIVE)
        .select_related('department', 'designation')
        .order_by('-start_date')
        .first()
    ) or (
        StaffEmployment.objects.filter(staff=staff)
        .select_related('department', 'designation')
        .order_by('-start_date')
        .first()
    )

    headed_depts = [
        {"id": str(d.id), "name": d.name, "code": d.code}
        for d in staff.headed_departments.filter(is_active=True)
    ]

    # 3. Teaching Assignments for Target Session
    assignments_qs = TeacherAssignment.objects.none()
    if target_session:
        assignments_qs = (
            TeacherAssignment.objects.filter(
                staff=staff,
                academic_session=target_session,
                is_active=True,
            )
            .select_related('class_obj', 'class_arm', 'subject', 'academic_session')
            .order_by('class_obj__name', 'subject__name')
        )

    assignments = list(assignments_qs)
    is_academic_category = (
        active_employment is not None
        and active_employment.designation.category == Designation.Category.ACADEMIC
    )
    is_teaching_staff = bool(is_academic_category or len(assignments) > 0)

    # 4. Precompute Enrolled Student Counts & Score Progress for Assigned Classes
    assigned_class_ids = {a.class_obj_id for a in assignments}
    class_enrollments_qs = StudentEnrollment.objects.none()
    if target_session and assigned_class_ids:
        class_enrollments_qs = StudentEnrollment.objects.filter(
            academic_session=target_session,
            class_obj_id__in=assigned_class_ids,
            status='ENROLLED',
        )

    # Map (class_id, class_arm_id) and (class_id, None) to student counts in one query
    arm_counts_map = {}
    class_totals_map = {}
    for row in class_enrollments_qs.values('class_obj_id', 'class_arm_id').annotate(cnt=Count('id')):
        c_id = row['class_obj_id']
        a_id = row['class_arm_id']
        arm_counts_map[(c_id, a_id)] = row['cnt']
        class_totals_map[c_id] = class_totals_map.get(c_id, 0) + row['cnt']

    # Precompute score submission progress per (class_id, subject_id) for target_term
    score_stats_map = {}
    if target_term and assigned_class_ids:
        score_rows = (
            StudentScore.objects.filter(
                academic_term=target_term,
                student_enrollment__academic_session=target_session,
                student_enrollment__class_obj_id__in=assigned_class_ids,
            )
            .values('student_enrollment__class_obj_id', 'subject_id')
            .annotate(
                total_entries=Count('id'),
                draft_entries=Count('id', filter=Q(status=StudentScore.ScoreSubmissionStatus.DRAFT)),
                submitted_entries=Count('id', filter=Q(status=StudentScore.ScoreSubmissionStatus.SUBMITTED)),
            )
        )
        for s_row in score_rows:
            key = (s_row['student_enrollment__class_obj_id'], s_row['subject_id'])
            score_stats_map[key] = {
                "total_entries": s_row['total_entries'],
                "draft_entries": s_row['draft_entries'],
                "submitted_entries": s_row['submitted_entries'],
            }

    class_teacher_classes = []
    subject_assignments = []
    authorized_arm_filters = Q()

    for asn in assignments:
        student_count = (
            arm_counts_map.get((asn.class_obj_id, asn.class_arm_id), 0)
            if asn.class_arm_id
            else class_totals_map.get(asn.class_obj_id, 0)
        )

        if asn.class_arm_id:
            authorized_arm_filters |= Q(class_obj_id=asn.class_obj_id, class_arm_id=asn.class_arm_id)
        else:
            authorized_arm_filters |= Q(class_obj_id=asn.class_obj_id)

        if asn.is_class_teacher or asn.assignment_type == TeacherAssignment.AssignmentType.CLASS_TEACHER:
            class_teacher_classes.append({
                "assignment_id": str(asn.id),
                "class_id": str(asn.class_obj_id),
                "class_name": asn.class_obj.name,
                "class_arm_id": str(asn.class_arm_id) if asn.class_arm_id else None,
                "class_arm_name": asn.class_arm.name if asn.class_arm else None,
                "student_count": student_count,
            })

        if asn.subject_id:
            s_stats = score_stats_map.get(
                (asn.class_obj_id, asn.subject_id),
                {"total_entries": 0, "draft_entries": 0, "submitted_entries": 0},
            )
            subject_assignments.append({
                "assignment_id": str(asn.id),
                "assignment_type": asn.assignment_type,
                "class_id": str(asn.class_obj_id),
                "class_name": asn.class_obj.name,
                "class_arm_id": str(asn.class_arm_id) if asn.class_arm_id else None,
                "class_arm_name": asn.class_arm.name if asn.class_arm else None,
                "subject_id": str(asn.subject_id),
                "subject_name": asn.subject.name,
                "subject_code": asn.subject.code,
                "student_count": student_count,
                "term_score_progress": s_stats,
            })

    # 5. Students in Authorized Classes (Count + Roster Preview of up to 20 students)
    authorized_students_preview = []
    total_authorized_students = 0
    if target_session and assigned_class_ids and authorized_arm_filters:
        auth_enrollments_qs = (
            StudentEnrollment.objects.filter(
                academic_session=target_session,
                status='ENROLLED',
            )
            .filter(authorized_arm_filters)
            .select_related('student__user', 'class_obj', 'class_arm')
            .order_by('class_obj__name', 'student__last_name', 'student__first_name')
        )
        total_authorized_students = auth_enrollments_qs.count()
        for enr in auth_enrollments_qs[:20]:
            st = enr.student
            authorized_students_preview.append({
                "enrollment_id": str(enr.id),
                "student_id": str(st.id),
                "admission_number": st.user.login_id if st.user else None,
                "full_name": f"{st.last_name}, {st.first_name} {st.middle_name or ''}".strip(),
                "gender": st.gender,
                "class_name": enr.class_obj.name,
                "class_arm": enr.class_arm.name if enr.class_arm else None,
            })

    # 6. Recent Academic & Examination Activities (Active Term)
    upcoming_examinations = []
    recent_score_submissions = []
    if target_term:
        exams_qs = Examination.objects.filter(
            academic_term=target_term,
            is_active=True,
        ).order_by('start_date')[:5]
        upcoming_examinations = [
            {
                "id": str(ex.id),
                "name": ex.name,
                "examination_type": ex.examination_type,
                "start_date": str(ex.start_date),
                "end_date": str(ex.end_date),
                "status": ex.status,
            }
            for ex in exams_qs
        ]

        audits_qs = (
            ResultWorkflowAudit.objects.filter(
                academic_term=target_term,
                performed_by=user,
            )
            .select_related('class_obj', 'class_arm', 'subject')
            .order_by('-created_at')[:5]
        )
        recent_score_submissions = [
            {
                "id": str(a.id),
                "class_name": a.class_obj.name,
                "class_arm": a.class_arm.name if a.class_arm else None,
                "subject": a.subject.name if a.subject else None,
                "previous_status": a.previous_status,
                "new_status": a.new_status,
                "reason": a.reason,
                "timestamp": a.created_at.isoformat(),
            }
            for a in audits_qs
        ]

    return {
        "school_context": {
            "school_name": getattr(settings_obj, 'school_name', 'Almawrid Islamic International College'),
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
        "staff_profile": {
            "profile_id": str(staff.id),
            "staff_id": user.login_id,
            "full_name": f"{staff.last_name}, {staff.first_name} {staff.middle_name or ''}".strip(),
            "first_name": staff.first_name,
            "last_name": staff.last_name,
            "email": user.email,
            "phone_number": staff.phone_number,
            "gender": staff.gender,
            "is_teaching_staff": is_teaching_staff,
            "qualifications_count": staff.qualifications.count(),
            "headed_departments": headed_depts,
        },
        "employment": {
            "employment_id": str(active_employment.id),
            "department_id": str(active_employment.department_id),
            "department_name": active_employment.department.name,
            "department_code": active_employment.department.code,
            "designation_id": str(active_employment.designation_id),
            "designation_name": active_employment.designation.name,
            "designation_code": active_employment.designation.code,
            "category": active_employment.designation.category,
            "category_display": active_employment.designation.get_category_display(),
            "employment_type": active_employment.employment_type,
            "status": active_employment.status,
            "start_date": str(active_employment.start_date),
        } if active_employment else None,
        "teaching_overview": {
            "has_teaching_assignments": len(assignments) > 0,
            "total_assigned_classes": len(assigned_class_ids),
            "total_subject_assignments": len(subject_assignments),
            "is_class_teacher": len(class_teacher_classes) > 0,
            "total_students_in_authorized_classes": total_authorized_students,
            "class_teacher_assignments": class_teacher_classes,
            "subject_assignments": subject_assignments,
            "authorized_students_preview": authorized_students_preview,
        },
        "recent_academic_activities": {
            "active_term_examinations": upcoming_examinations,
            "my_recent_workflow_actions": recent_score_submissions,
        },
    }