from django.db.models import Q

from apps.academics.models import (
    SchoolSettings,
    AcademicSession,
    AcademicTerm,
    ClassSubject,
)
from apps.examinations.models import (
    Examination,
    StudentResult,
    StudentTermSummary,
    ResultWorkflowStatus,
)
from apps.staff.models import TeacherAssignment
from apps.students.models import Student, StudentEnrollment


# Append to apps/dashboard/services.py:
def build_student_dashboard_payload(user, session_id=None, term_id=None) -> dict:
    """
    Constructs the Student Dashboard payload strictly for the authenticated student (`user.student_profile`).
    Never exposes unpublished or unapproved examination results.
    """
    settings_obj = SchoolSettings.load()
    student = (
        Student.objects.select_related('user')
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

    # 2. Fetch Enrollment History & Resolve Current Session Enrollment
    all_enrollments = list(
        StudentEnrollment.objects.filter(student=student)
        .select_related('academic_session', 'academic_term', 'class_obj', 'class_arm')
        .order_by('-academic_session__start_date', '-created_at')
    )

    current_enrollment = None
    if target_session:
        current_enrollment = next(
            (e for e in all_enrollments if e.academic_session_id == target_session.id),
            None
        )
    if not current_enrollment and all_enrollments:
        current_enrollment = all_enrollments[0]

    # 3. Resolve Assigned Class Teacher & Offered Subjects for Current Enrollment
    class_teacher_info = None
    assigned_subjects = []
    classmates_count = 0

    if current_enrollment:
        enr_session = current_enrollment.academic_session
        enr_class = current_enrollment.class_obj
        enr_arm = current_enrollment.class_arm

        # Count active classmates in the same class (and arm if applicable)
        classmates_qs = StudentEnrollment.objects.filter(
            academic_session=enr_session,
            class_obj=enr_class,
            status='ENROLLED',
        )
        if enr_arm:
            classmates_qs = classmates_qs.filter(class_arm=enr_arm)
        classmates_count = classmates_qs.count()

        # Fetch active teacher assignments for this class and session in a single query
        teacher_assignments = list(
            TeacherAssignment.objects.filter(
                academic_session=enr_session,
                class_obj=enr_class,
                is_active=True,
            )
            .filter(Q(class_arm=enr_arm) | Q(class_arm__isnull=True))
            .select_related('staff__user', 'subject', 'class_arm')
        )

        # Find Form Master / Class Teacher (prefer exact arm match over whole-class match)
        form_masters = [
            ta for ta in teacher_assignments
            if ta.is_class_teacher or ta.assignment_type == TeacherAssignment.AssignmentType.CLASS_TEACHER
        ]
        form_masters.sort(key=lambda x: 0 if (enr_arm and x.class_arm_id == enr_arm.id) else 1)
        if form_masters:
            fm = form_masters[0].staff
            class_teacher_info = {
                "staff_id": fm.user.login_id if fm.user else None,
                "full_name": f"{fm.last_name}, {fm.first_name} {fm.middle_name or ''}".strip(),
                "email": fm.user.email if fm.user else None,
            }

        # Map subject_id -> teacher name
        subject_teacher_map = {}
        for ta in teacher_assignments:
            if ta.subject_id:
                stf = ta.staff
                t_name = f"{stf.last_name}, {stf.first_name}".strip()
                # Prefer arm-specific teacher if multiple exist
                if ta.subject_id not in subject_teacher_map or (enr_arm and ta.class_arm_id == enr_arm.id):
                    subject_teacher_map[ta.subject_id] = t_name

        # Fetch subjects offered by the student's class
        class_subjects = (
            ClassSubject.objects.filter(class_obj=enr_class, is_active=True)
            .select_related('subject')
            .order_by('subject__name')
        )
        for cs in class_subjects:
            subj = cs.subject
            assigned_subjects.append({
                "subject_id": str(subj.id),
                "name": subj.name,
                "code": subj.code,
                "is_compulsory": getattr(cs, 'is_compulsory', getattr(subj, 'is_compulsory', True)),
                "subject_teacher": subject_teacher_map.get(subj.id),
            })

    # 4. Published Examination Results (Strictly PUBLISHED or LOCKED only)
    published_states = [ResultWorkflowStatus.PUBLISHED, ResultWorkflowStatus.LOCKED]
    published_summaries_qs = (
        StudentTermSummary.objects.filter(
            student_enrollment__student=student,
            status__in=published_states,
        )
        .select_related(
            'student_enrollment__academic_session',
            'student_enrollment__class_obj',
            'student_enrollment__class_arm',
            'academic_term',
        )
        .order_by('-academic_term__start_date', '-published_at')
    )

    published_summaries = []
    latest_term_subject_breakdown = []

    for idx, summary in enumerate(published_summaries_qs):
        published_summaries.append({
            "term_summary_id": str(summary.id),
            "session_id": str(summary.student_enrollment.academic_session_id),
            "session_name": summary.student_enrollment.academic_session.name,
            "term_id": str(summary.academic_term_id),
            "term_name": summary.academic_term.get_name_display(),
            "class_name": summary.student_enrollment.class_obj.name,
            "class_arm": summary.student_enrollment.class_arm.name if summary.student_enrollment.class_arm else None,
            "subjects_offered": summary.subjects_offered,
            "subjects_passed": summary.subjects_passed,
            "total_score": str(summary.total_score),
            "average_score": str(summary.average_score),
            "gpa": str(summary.gpa),
            "class_position": summary.class_position,
            "arm_position": summary.arm_position,
            "total_students_in_class": summary.total_students_in_class,
            "teacher_remarks": summary.teacher_remarks or "",
            "principal_remarks": summary.principal_remarks or "",
            "published_at": summary.published_at.isoformat() if summary.published_at else None,
            "report_card_url": f"/api/v1/examinations/term-summaries/{summary.id}/report-card/",
            "report_card_pdf_url": f"/api/v1/examinations/term-summaries/{summary.id}/report-card/?export=pdf",
        })

        # Populate subject-level breakdown for the most recent published result (or target_term if published)
        is_target_match = (target_term and summary.academic_term_id == target_term.id)
        if (idx == 0 and not latest_term_subject_breakdown) or is_target_match:
            subj_results = (
                StudentResult.objects.filter(
                    student_enrollment=summary.student_enrollment,
                    academic_term=summary.academic_term,
                    status__in=published_states,
                )
                .select_related('subject')
                .order_by('subject__name')
            )
            latest_term_subject_breakdown = [
                {
                    "subject_id": str(sr.subject_id),
                    "subject_name": sr.subject.name,
                    "subject_code": sr.subject.code,
                    "ca_total": str(sr.ca_total),
                    "exam_score": str(sr.exam_score),
                    "total_score": str(sr.total_score),
                    "grade": sr.grade,
                    "grade_point": str(sr.grade_point),
                    "remark": sr.remark,
                    "subject_position": sr.subject_position,
                }
                for sr in subj_results
            ]

    # 5. Active Term Examination Schedule for Student's Class
    upcoming_exams = []
    if target_term and current_enrollment:
        exams_qs = (
            Examination.objects.filter(
                academic_term=target_term,
                is_active=True,
            )
            .filter(
                Q(applicable_classes=current_enrollment.class_obj)
                | Q(applicable_classes__isnull=True)
            )
            .distinct()
            .order_by('start_date')[:5]
        )
        upcoming_exams = [
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

    # 6. Academic Enrollment History
    enrollment_history = [
        {
            "enrollment_id": str(enr.id),
            "session_id": str(enr.academic_session_id),
            "session_name": enr.academic_session.name,
            "term_name": enr.academic_term.get_name_display() if enr.academic_term else None,
            "class_id": str(enr.class_obj_id),
            "class_name": enr.class_obj.name,
            "class_arm": enr.class_arm.name if enr.class_arm else None,
            "status": enr.status,
            "enrollment_date": str(enr.enrollment_date) if enr.enrollment_date else None,
        }
        for enr in all_enrollments
    ]

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
        "student_profile": {
            "profile_id": str(student.id),
            "admission_number": user.login_id,
            "first_name": student.first_name,
            "middle_name": student.middle_name,
            "last_name": student.last_name,
            "full_name": f"{student.last_name}, {student.first_name} {student.middle_name or ''}".strip(),
            "gender": student.gender,
            "date_of_birth": str(student.date_of_birth) if student.date_of_birth else None,
            "nationality": student.nationality,
            "state_of_origin": student.state_of_origin,
        },
        "current_enrollment": {
            "enrollment_id": str(current_enrollment.id),
            "session_id": str(current_enrollment.academic_session_id),
            "session_name": current_enrollment.academic_session.name,
            "class_id": str(current_enrollment.class_obj_id),
            "class_name": current_enrollment.class_obj.name,
            "education_level": current_enrollment.class_obj.education_level,
            "class_arm_id": str(current_enrollment.class_arm_id) if current_enrollment.class_arm_id else None,
            "class_arm_name": current_enrollment.class_arm.name if current_enrollment.class_arm else None,
            "status": current_enrollment.status,
            "classmates_count": classmates_count,
            "class_teacher": class_teacher_info,
            "assigned_subjects_count": len(assigned_subjects),
            "assigned_subjects": assigned_subjects,
        } if current_enrollment else None,
        "examinations_and_results": {
            "published_terms_count": len(published_summaries),
            "published_term_summaries": published_summaries,
            "latest_published_subject_results": latest_term_subject_breakdown,
            "active_term_examinations": upcoming_exams,
        },
        "enrollment_history": enrollment_history,
    }