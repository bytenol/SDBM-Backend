import io
from django.http import HttpResponse
from apps.academics.models import SchoolSettings
from .models import StudentResult, StudentScore, StudentTermSummary


def build_report_card_payload(summary: StudentTermSummary) -> dict:
    """
    Constructs a complete, structured report card dictionary for a StudentTermSummary instance.
    """
    settings_obj = SchoolSettings.load()
    enrollment = summary.student_enrollment
    student = enrollment.student
    term = summary.academic_term
    session = enrollment.academic_session

    subject_results = StudentResult.objects.filter(
        student_enrollment=enrollment,
        academic_term=term
    ).select_related('subject').order_by('subject__name')

    raw_scores = StudentScore.objects.filter(
        student_enrollment=enrollment,
        academic_term=term
    ).select_related('assessment_component')

    # Group component breakdowns by subject_id
    breakdown_map = {}
    for s in raw_scores:
        breakdown_map.setdefault(s.subject_id, []).append({
            "component_code": s.assessment_component.code,
            "component_name": s.assessment_component.name,
            "raw_score": str(s.score) if s.score is not None else None,
            "max_score": str(s.max_score_snapshot),
            "weighted_score": str(s.weighted_score),
            "is_absent": s.is_absent,
            "is_exempted": s.is_exempted,
        })

    subjects_payload = []
    for res in subject_results:
        subjects_payload.append({
            "subject_id": str(res.subject_id),
            "subject_name": res.subject.name,
            "subject_code": res.subject.code,
            "ca_total": str(res.ca_total),
            "exam_score": str(res.exam_score),
            "total_score": str(res.total_score),
            "grade": res.grade,
            "grade_point": str(res.grade_point),
            "remark": res.remark,
            "subject_position": res.subject_position,
            "class_highest": str(res.class_highest),
            "class_lowest": str(res.class_lowest),
            "class_average": str(res.class_average),
            "components": breakdown_map.get(res.subject_id, []),
        })

    return {
        "school_info": {
            "school_name": getattr(settings_obj, 'school_name', 'Almawrid Islamic International College'),
            "school_motto": getattr(settings_obj, 'school_motto', ''),
            "school_address": getattr(settings_obj, 'address', ''),
        },
        "student_info": {
            "student_id": str(student.id),
            "admission_number": student.user.login_id,
            "full_name": f"{student.last_name}, {student.first_name} {student.middle_name or ''}".strip(),
            "gender": student.gender,
            "date_of_birth": str(student.date_of_birth) if student.date_of_birth else None,
        },
        "academic_context": {
            "session": session.name,
            "term": term.get_name_display(),
            "class": enrollment.class_obj.name,
            "class_arm": enrollment.class_arm.name if enrollment.class_arm else None,
        },
        "performance_summary": {
            "subjects_offered": summary.subjects_offered,
            "subjects_passed": summary.subjects_passed,
            "total_score": str(summary.total_score),
            "average_score": str(summary.average_score),
            "gpa": str(summary.gpa),
            "class_position": summary.class_position,
            "arm_position": summary.arm_position,
            "total_students_in_class": summary.total_students_in_class,
        },
        "subjects": subjects_payload,
        "remarks_and_approval": {
            "teacher_remarks": summary.teacher_remarks or "",
            "principal_remarks": summary.principal_remarks or "",
            "status": summary.status,
            "published_at": summary.published_at.isoformat() if summary.published_at else None,
        },
    }


def generate_report_card_pdf_response(report_data: dict) -> HttpResponse:
    """
    Generates a clean downloadable PDF report card.
    Uses reportlab if installed; otherwise falls back to a formatted plain-text/HTML stream.
    """
    admission_no = report_data['student_info']['admission_number']
    term_label = report_data['academic_context']['term'].replace(' ', '_')
    filename = f"ReportCard_{admission_no}_{term_label}.pdf"

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        # Header
        p.setFont("Helvetica-Bold", 16)
        p.drawCentredString(width / 2, height - 50, report_data['school_info']['school_name'])
        p.setFont("Helvetica", 11)
        p.drawCentredString(
            width / 2,
            height - 70,
            f"STUDENT TERM REPORT CARD — {report_data['academic_context']['session']} ({report_data['academic_context']['term']})"
        )

        # Student Metadata
        y = height - 110
        p.setFont("Helvetica-Bold", 10)
        p.drawString(40, y, f"Name: {report_data['student_info']['full_name']}")
        p.drawString(350, y, f"Admission No: {admission_no}")
        y -= 18
        p.drawString(40, y, f"Class: {report_data['academic_context']['class']} {report_data['academic_context']['class_arm'] or ''}")
        perf = report_data['performance_summary']
        p.drawString(350, y, f"Average: {perf['average_score']}% | GPA: {perf['gpa']}")

        # Table Header
        y -= 30
        p.setFont("Helvetica-Bold", 9)
        p.drawString(40, y, "Subject")
        p.drawString(220, y, "CA")
        p.drawString(270, y, "Exam")
        p.drawString(320, y, "Total")
        p.drawString(370, y, "Grade")
        p.drawString(420, y, "Remark")
        p.line(40, y - 4, width - 40, y - 4)

        # Subject Rows
        p.setFont("Helvetica", 9)
        y -= 20
        for subj in report_data['subjects']:
            if y < 100:
                p.showPage()
                y = height - 60
            p.drawString(40, y, subj['subject_name'][:30])
            p.drawString(220, y, subj['ca_total'])
            p.drawString(270, y, subj['exam_score'])
            p.drawString(320, y, subj['total_score'])
            p.drawString(370, y, str(subj['grade'] or '-'))
            p.drawString(420, y, str(subj['remark'] or '-'))
            y -= 16

        # Remarks Footer
        y -= 20
        p.line(40, y, width - 40, y)
        y -= 18
        p.setFont("Helvetica-Oblique", 9)
        p.drawString(40, y, f"Teacher's Remark: {report_data['remarks_and_approval']['teacher_remarks']}")
        y -= 16
        p.drawString(40, y, f"Principal's Remark: {report_data['remarks_and_approval']['principal_remarks']}")

        p.showPage()
        p.save()
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except ImportError:
        # Fallback if reportlab is not yet installed in virtualenv
        content = f"REPORT CARD: {report_data['student_info']['full_name']} ({admission_no})\n"
        response = HttpResponse(content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response