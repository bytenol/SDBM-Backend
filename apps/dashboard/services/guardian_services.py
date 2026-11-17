from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from apps.academics.models import AcademicSession, AcademicTerm, SchoolSettings
from apps.dashboard.services.dashboard_services import get_parent_guardian_links_queryset
from apps.examinations.models import ResultWorkflowStatus, StudentResult, StudentTermSummary
from apps.staff.models import TeacherAssignment
from apps.students.models import StudentEnrollment


def build_parent_dashboard_payload(user, session_id=None, term_id=None, student_id=None) -> dict:
    """
    Constructs the Parent Dashboard payload for an authenticated guardian (`user`).
    Supports parents with multiple linked children and enforces strict IDOR protection
    when filtering by `student_id`. Only exposes PUBLISHED or LOCKED examination results.
    """
    settings_obj = SchoolSettings.load()

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

    # 2. Fetch all linked StudentGuardian records for this authenticated parent
    guardian_links_qs = (
        get_parent_guardian_links_queryset(user)
        .select_related('student__user')
        .order_by('student__last_name', 'student__first_name')
    )
    all_links = list(guardian_links_qs)
    linked_student_ids = {link.student_id for link in all_links}

    # Strict IDOR check if a specific student_id filter is requested
    if student_id:
        if student_id not in linked_student_ids:
            raise PermissionDenied("You are not authorized to access records for this student.")
        active_links = [link for link in all_links if link.student_id == student_id]
    else:
        active_links = all_links

    target_student_ids = [link.student_id for link in active_links]

    # 3. Batch-fetch enrollments for all linked children (Zero N+1 queries)
    enrollments_by_student = {}
    involved_class_ids = set()
    if target_student_ids:
        enrollments_qs = (
            StudentEnrollment.objects.filter(student_id__in=target_student_ids)
            .select_related('academic_session', 'academic_term', 'class_obj', 'class_arm')
            .order_by('-academic_session__start_date', '-created_at')
        )
        for enr in enrollments_qs:
            enrollments_by_student.setdefault(enr.student_id, []).append(enr)
            involved_class_ids.add(enr.class_obj_id)

    # 4. Batch-fetch Form Masters (Class Teachers) for the children's classes
    class_teachers_by_class = {}
    if target_session and involved_class_ids:
        ct_qs = (
            TeacherAssignment.objects.filter(
                academic_session=target_session,
                class_obj_id__in=involved_class_ids,
                is_active=True,
            )
            .filter(
                Q(is_class_teacher=True)
                | Q(assignment_type=TeacherAssignment.AssignmentType.CLASS_TEACHER)
            )
            .select_related('staff__user')
        )
        for ct in ct_qs:
            class_teachers_by_class.setdefault(ct.class_obj_id, []).append(ct)

    # 5. Batch-fetch PUBLISHED / LOCKED Term Summaries & Subject Results for all linked children
    published_states = [ResultWorkflowStatus.PUBLISHED, ResultWorkflowStatus.LOCKED]
    summaries_by_student = {}
    results_by_enrollment_term = {}

    if target_student_ids:
        published_summaries_qs = (
            StudentTermSummary.objects.filter(
                student_enrollment__student_id__in=target_student_ids,
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
        for summary in published_summaries_qs:
            s_id = summary.student_enrollment.student_id
            summaries_by_student.setdefault(s_id, []).append(summary)

        published_subj_results_qs = (
            StudentResult.objects.filter(
                student_enrollment__student_id__in=target_student_ids,
                status__in=published_states,
            )
            .select_related('subject')
            .order_by('subject__name')
        )
        for sr in published_subj_results_qs:
            key = (sr.student_enrollment_id, sr.academic_term_id)
            results_by_enrollment_term.setdefault(key, []).append(sr)

    # 6. Assemble Child Dashboard Cards
    children_cards = []
    total_published_reports = 0

    for link in active_links:
        student = link.student
        student_enrollments = enrollments_by_student.get(student.id, [])

        current_enr = None
        if target_session:
            current_enr = next(
                (e for e in student_enrollments if e.academic_session_id == target_session.id),
                None
            )
        if not current_enr and student_enrollments:
            current_enr = student_enrollments[0]

        # Resolve Form Master / Class Teacher for current enrollment
        class_teacher_data = None
        if current_enr:
            candidates = class_teachers_by_class.get(current_enr.class_obj_id, [])
            candidates.sort(
                key=lambda x: 0 if (current_enr.class_arm_id and x.class_arm_id == current_enr.class_arm_id) else 1
            )
            if candidates:
                fm = candidates[0].staff
                class_teacher_data = {
                    "staff_id": fm.user.login_id if fm.user else None,
                    "full_name": f"{fm.last_name}, {fm.first_name} {fm.middle_name or ''}".strip(),
                    "phone_number": fm.phone_number,
                    "email": fm.user.email if fm.user else None,
                }

        # Format published term summaries for this child
        child_summaries = summaries_by_student.get(student.id, [])
        total_published_reports += len(child_summaries)

        formatted_summaries = []
        latest_subject_breakdown = []

        for idx, sm in enumerate(child_summaries):
            formatted_summaries.append({
                "term_summary_id": str(sm.id),
                "session_id": str(sm.student_enrollment.academic_session_id),
                "session_name": sm.student_enrollment.academic_session.name,
                "term_id": str(sm.academic_term_id),
                "term_name": sm.academic_term.get_name_display(),
                "class_name": sm.student_enrollment.class_obj.name,
                "class_arm": sm.student_enrollment.class_arm.name if sm.student_enrollment.class_arm else None,
                "subjects_offered": sm.subjects_offered,
                "subjects_passed": sm.subjects_passed,
                "total_score": str(sm.total_score),
                "average_score": str(sm.average_score),
                "gpa": str(sm.gpa),
                "class_position": sm.class_position,
                "arm_position": sm.arm_position,
                "total_students_in_class": sm.total_students_in_class,
                "teacher_remarks": sm.teacher_remarks or "",
                "principal_remarks": sm.principal_remarks or "",
                "published_at": sm.published_at.isoformat() if sm.published_at else None,
                "report_card_url": f"/api/v1/examinations/term-summaries/{sm.id}/report-card/",
                "report_card_pdf_url": f"/api/v1/examinations/term-summaries/{sm.id}/report-card/?export=pdf",
            })

            is_target_term_match = (target_term and sm.academic_term_id == target_term.id)
            if (idx == 0 and not latest_subject_breakdown) or is_target_term_match:
                subj_list = results_by_enrollment_term.get((sm.student_enrollment_id, sm.academic_term_id), [])
                latest_subject_breakdown = [
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
                    for sr in subj_list
                ]

        relationship_val = (
            getattr(link, 'relationship', None)
            or getattr(link, 'relationship_type', None)
            or getattr(link, 'relation', None)
            or 'GUARDIAN'
        )
        is_primary_val = bool(
            getattr(link, 'is_primary', False)
            or getattr(link, 'is_primary_guardian', False)
        )

        children_cards.append({
            "student_profile": {
                "student_id": str(student.id),
                "admission_number": student.user.login_id if student.user else None,
                "first_name": student.first_name,
                "middle_name": student.middle_name,
                "last_name": student.last_name,
                "full_name": f"{student.last_name}, {student.first_name} {student.middle_name or ''}".strip(),
                "gender": student.gender,
                "date_of_birth": str(student.date_of_birth) if student.date_of_birth else None,
                "relationship": relationship_val,
                "is_primary_guardian": is_primary_val,
            },
            "current_enrollment": {
                "enrollment_id": str(current_enr.id),
                "session_id": str(current_enr.academic_session_id),
                "session_name": current_enr.academic_session.name,
                "class_id": str(current_enr.class_obj_id),
                "class_name": current_enr.class_obj.name,
                "education_level": current_enr.class_obj.education_level,
                "class_arm_id": str(current_enr.class_arm_id) if current_enr.class_arm_id else None,
                "class_arm_name": current_enr.class_arm.name if current_enr.class_arm else None,
                "status": current_enr.status,
                "class_teacher": class_teacher_data,
            } if current_enr else None,
            "academic_results": {
                "published_terms_count": len(formatted_summaries),
                "latest_term_summary": formatted_summaries[0] if formatted_summaries else None,
                "latest_subject_results": latest_subject_breakdown,
                "published_term_summaries": formatted_summaries,
            },
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
        "parent_profile": {
            "id": str(user.id),
            "login_id": user.login_id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "full_name": f"{user.first_name} {user.last_name}".strip(),
            "phone_number": getattr(user, 'phone_number', None),
        },
        "overview_metrics": {
            "total_linked_children": len(all_links),
            "displayed_children_count": len(children_cards),
            "total_published_report_cards": total_published_reports,
        },
        "children": children_cards,
    }