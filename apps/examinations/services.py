from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.db.models import Avg, Max, Min, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied

from apps.academics.models import AcademicSession, AcademicTerm, Class, ClassArm, Subject
from apps.audit.models import AuditAction, AuditCategory
from apps.audit.services import log_audit_event
from apps.students.models import StudentEnrollment
from apps.staff.models import TeacherAssignment
from .models import (
    AssessmentCategory,
    AssessmentComponent,
    GradingScale,
    ResultWorkflowStatus,
    StudentScore,
    StudentResult,
    StudentTermSummary,
    ResultWorkflowAudit,
)


def is_admin_user(user) -> bool:
    """Checks if the user holds administrative privileges."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.roles.filter(name__in=['SUPER_ADMIN', 'ADMIN']).exists()


def verify_teacher_subject_authority(user, academic_session, class_obj, subject, class_arm=None):
    """
    Ensures the requesting user is either an Admin/SuperAdmin or a Staff member
    explicitly assigned to teach this subject in the specified class and session.
    """
    if is_admin_user(user):
        return True

    if not hasattr(user, 'staff_profile'):
        raise PermissionDenied("Only authorized teaching staff or administrators can perform this operation.")

    assignment_qs = TeacherAssignment.objects.filter(
        staff=user.staff_profile,
        academic_session=academic_session,
        class_obj=class_obj,
        subject=subject,
        is_active=True,
    )

    if class_arm:
        # Teacher can be assigned to the specific arm OR across the whole class (class_arm__isnull=True)
        assignment_qs = assignment_qs.filter(Q(class_arm=class_arm) | Q(class_arm__isnull=True))

    if not assignment_qs.exists():
        raise PermissionDenied(
            f"You are not assigned to teach '{subject.name}' for '{class_obj.name}' in '{academic_session.name}'."
        )
    return True


def get_applicable_components(academic_session, academic_term, class_obj):
    """
    Retrieves active assessment components for a specific session, term, and class.
    Prioritizes class-specific components if configured; otherwise falls back to global components.
    """
    class_specific = AssessmentComponent.objects.filter(
        academic_session=academic_session,
        academic_term=academic_term,
        class_obj=class_obj,
        is_active=True
    ).order_by('display_order', 'code')

    if class_specific.exists():
        return class_specific

    return AssessmentComponent.objects.filter(
        academic_session=academic_session,
        academic_term=academic_term,
        class_obj__isnull=True,
        is_active=True
    ).order_by('display_order', 'code')


def resolve_grade_for_score(score: Decimal, academic_session: AcademicSession, education_level: str = None):
    """
    Finds the matching GradingScale record for a computed percentage score (0 - 100).
    Checks session + education_level -> session global -> default education_level -> default global.
    """
    rounded_score = score.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    search_scopes = [
        {'academic_session': academic_session, 'education_level': education_level},
        {'academic_session': academic_session, 'education_level__isnull': True},
        {'academic_session__isnull': True, 'education_level': education_level},
        {'academic_session__isnull': True, 'education_level__isnull': True},
    ]

    for scope in search_scopes:
        scale = GradingScale.objects.filter(
            is_active=True,
            min_score__lte=rounded_score,
            max_score__gte=rounded_score,
            **scope
        ).first()
        if scale:
            return scale

    return None


@transaction.atomic
def record_bulk_student_scores(validated_data, user):
    """
    Atomically validates and saves a batch of raw student scores for a given term, class,
    subject, and assessment component.
    """
    academic_term = AcademicTerm.objects.select_related('session').get(pk=validated_data['academic_term'])
    academic_session = academic_term.session
    class_obj = Class.objects.get(pk=validated_data['class_obj'])
    class_arm = ClassArm.objects.get(pk=validated_data['class_arm']) if validated_data.get('class_arm') else None
    subject = Subject.objects.get(pk=validated_data['subject'])
    component = AssessmentComponent.objects.get(pk=validated_data['assessment_component'])
    scores_payload = validated_data['scores']

    # 1. Verify teacher or admin permission
    verify_teacher_subject_authority(user, academic_session, class_obj, subject, class_arm)

    # 2. Verify component belongs to term and class scope
    if component.academic_term_id != academic_term.id:
        raise ValidationError({"assessment_component": "Component does not belong to the selected academic term."})
    if component.class_obj_id and component.class_obj_id != class_obj.id:
        raise ValidationError({"assessment_component": "Component is restricted to a different class."})

    # 3. Verify subject is offered by the class
    if not class_obj.class_subjects.filter(subject=subject, is_active=True).exists():
        raise ValidationError({"subject": f"Subject '{subject.name}' is not actively assigned to class '{class_obj.name}'."})

    # 4. Prevent modifications if results for this class/term/subject are locked or published
    locked_Statuses = [
        ResultWorkflowStatus.APPROVED,
        ResultWorkflowStatus.PUBLISHED,
        ResultWorkflowStatus.LOCKED,
    ]
    if StudentResult.objects.filter(
        student_enrollment__academic_session=academic_session,
        student_enrollment__class_obj=class_obj,
        academic_term=academic_term,
        subject=subject,
        status__in=locked_Statuses
    ).exists():
        raise ValidationError(
            "Results for this subject and class have already been approved or published and cannot be modified without reopening."
        )

    saved_scores = []
    for item in scores_payload:
        enrollment_id = item['student_enrollment']
        enrollment = StudentEnrollment.objects.select_related('student').filter(
            pk=enrollment_id,
            academic_session=academic_session,
            class_obj=class_obj,
        ).first()

        if not enrollment:
            raise ValidationError(
                f"Student enrollment '{enrollment_id}' is not valid for class '{class_obj.name}' in session '{academic_session.name}'."
            )

        if class_arm and enrollment.class_arm_id != class_arm.id:
            raise ValidationError(
                f"Student '{enrollment.student}' does not belong to class arm '{class_arm.name}'."
            )

        raw_score = item.get('score')
        is_absent = item.get('is_absent', False)
        is_exempted = item.get('is_exempted', False)

        if not is_absent and not is_exempted:
            if raw_score is None:
                raise ValidationError(f"A numeric score is required for student '{enrollment.student}'.")
            if raw_score > component.maximum_score:
                raise ValidationError(
                    f"Score {raw_score} for '{enrollment.student}' exceeds maximum score ({component.maximum_score}) for {component.code}."
                )

        score_obj, created = StudentScore.objects.get_or_create(
            student_enrollment=enrollment,
            academic_term=academic_term,
            subject=subject,
            assessment_component=component,
            defaults={
                'score': None if (is_absent or is_exempted) else raw_score,
                'is_absent': is_absent,
                'is_exempted': is_exempted,
                'max_score_snapshot': component.maximum_score,
                'weight_snapshot': component.weight_percentage,
                'entered_by': user,
                'last_modified_by': user,
                'remarks': item.get('remarks', ''),
            }
        )

        if not created:
            if score_obj.status == StudentScore.ScoreSubmissionStatus.SUBMITTED and not is_admin_user(user):
                raise PermissionDenied(
                    f"Score for '{enrollment.student}' has already been submitted and can only be modified by an administrator."
                )
            score_obj.score = None if (is_absent or is_exempted) else raw_score
            score_obj.is_absent = is_absent
            score_obj.is_exempted = is_exempted
            score_obj.last_modified_by = user
            if 'remarks' in item:
                score_obj.remarks = item['remarks']
            score_obj.full_clean()
            score_obj.save()

        saved_scores.append(score_obj)


    # Emit Audit Log Event
    log_audit_event(
        action=AuditAction.CREATE,
        category=AuditCategory.EXAMINATIONS,
        description=f"Recorded/updated {len(saved_scores)} student score(s) for Component {component.code} in Term.",
        actor=user,
        metadata={
            "subject_id": str(subject),
            "component_code": component.code,
            "scores_count": len(saved_scores),
        },
    )

    return saved_scores


@transaction.atomic
def submit_subject_scores(academic_term_id, class_id, subject_id, user, class_arm_id=None):
    """
    Transitions all DRAFT scores for a subject/class/term to SUBMITTED and logs an audit entry.
    """
    academic_term = AcademicTerm.objects.select_related('session').get(pk=academic_term_id)
    academic_session = academic_term.session
    class_obj = Class.objects.get(pk=class_id)
    class_arm = ClassArm.objects.get(pk=class_arm_id) if class_arm_id else None
    subject = Subject.objects.get(pk=subject_id)

    verify_teacher_subject_authority(user, academic_session, class_obj, subject, class_arm)

    scores_qs = StudentScore.objects.filter(
        student_enrollment__academic_session=academic_session,
        student_enrollment__class_obj=class_obj,
        academic_term=academic_term,
        subject=subject,
    )

    count = scores_qs.update(
        status=StudentScore.ScoreSubmissionStatus.SUBMITTED,
        last_modified_by=user,
    )

    if count == 0:
        raise ValidationError("No draft score records found to submit for this class and subject.")

    if class_arm:
        scores_qs = scores_qs.filter(student_enrollment__class_arm=class_arm)

    if not scores_qs.exists():
        raise ValidationError("No recorded scores found to submit for the specified class and subject.")

    now = timezone.now()
    updated_count = scores_qs.filter(status=StudentScore.ScoreSubmissionStatus.DRAFT).update(
        status=StudentScore.ScoreSubmissionStatus.SUBMITTED,
        submitted_at=now,
        last_modified_by=user,
    )

    ResultWorkflowAudit.objects.create(
        academic_session=academic_session,
        academic_term=academic_term,
        class_obj=class_obj,
        class_arm=class_arm,
        subject=subject,
        previous_status=ResultWorkflowStatus.DRAFT,
        new_status=ResultWorkflowStatus.SCORES_SUBMITTED,
        performed_by=user,
        reason=f"Submitted {updated_count} score record(s) for review."
    )

    log_audit_event(
        action=AuditAction.UPDATE,
        category=AuditCategory.EXAMINATIONS,
        description=f"Submitted {count} score record(s) for review (Subject: {subject_id}, Class: {class_id}).",
        actor=user,
        metadata={
            "term_id": str(academic_term_id),
            "class_id": str(class_id),
            "subject_id": str(subject_id),
            "submitted_count": count,
        },
    )

    return updated_count


def _assign_standard_rankings(records, score_field: str, position_field: str):
    """
    Applies standard competition ranking (1, 2, 2, 4) in descending order of score_field.
    """
    sorted_records = sorted(records, key=lambda r: getattr(r, score_field), reverse=True)
    current_rank = 0
    previous_score = None

    for idx, record in enumerate(sorted_records, start=1):
        val = getattr(record, score_field)
        if val != previous_score:
            current_rank = idx
            previous_score = val
        setattr(record, position_field, current_rank)
        record.save(update_fields=[position_field])


@transaction.atomic
def compute_class_term_results(academic_term_id, class_id, user, class_arm_id=None):
    """
    Comprehensive Result Computation Engine:
    1. Validates assessment component weights equal 100%.
    2. Computes subject-level CA totals, exam scores, normalized totals, and grades.
    3. Calculates subject statistics (highest, lowest, average) and subject positions.
    4. Aggregates StudentTermSummary (overall total, average, GPA, class/arm positions).
    """
    if not is_admin_user(user):
        raise PermissionDenied("Only administrators can trigger full class result computations.")

    academic_term = AcademicTerm.objects.select_related('session').get(pk=academic_term_id)
    academic_session = academic_term.session
    class_obj = Class.objects.get(pk=class_id)
    class_arm = ClassArm.objects.get(pk=class_arm_id) if class_arm_id else None

    components = list(get_applicable_components(academic_session, academic_term, class_obj))
    if not components:
        raise ValidationError(f"No active assessment components configured for '{class_obj.name}' in '{academic_term}'.")

    total_weight = sum((c.weight_percentage for c in components), Decimal('0.00'))
    if total_weight != Decimal('100.00'):
        raise ValidationError(
            f"Active assessment component weights for '{class_obj.name}' sum to {total_weight}%, but must equal 100.00%."
        )

    enrollments_qs = StudentEnrollment.objects.filter(
        academic_session=academic_session,
        class_obj=class_obj,
        status=StudentEnrollment.EnrollmentStatus.ENROLLED
    ).select_related('student')

    if class_arm:
        enrollments_qs = enrollments_qs.filter(class_arm=class_arm)

    enrollments = list(enrollments_qs)
    if not enrollments:
        raise ValidationError("No active student enrollments found for the selected class/arm.")

    # Check if results are already locked or published
    if StudentTermSummary.objects.filter(
        student_enrollment__in=enrollments,
        academic_term=academic_term,
        status__in=[ResultWorkflowStatus.APPROVED, ResultWorkflowStatus.PUBLISHED, ResultWorkflowStatus.LOCKED]
    ).exists():
        raise ValidationError(
            "Cannot recompute results that are already APPROVED, PUBLISHED, or LOCKED. Reopen the results first."
        )

    now = timezone.now()
    subjects_affected = set()

    # Step A: Compute Subject-Level Results for each enrolled student
    for enrollment in enrollments:
        student_scores = StudentScore.objects.filter(
            student_enrollment=enrollment,
            academic_term=academic_term
        ).select_related('assessment_component', 'subject')

        # Group scores by subject_id
        scores_by_subject = {}
        for s in student_scores:
            scores_by_subject.setdefault(s.subject_id, {})[s.assessment_component_id] = s
            subjects_affected.add(s.subject)

        for subject_id, comp_map in scores_by_subject.items():
            subject_obj = next(s for s in subjects_affected if s.id == subject_id)
            ca_sum = Decimal('0.00')
            exam_sum = Decimal('0.00')
            exempted_weight = Decimal('0.00')
            is_incomplete = False

            for comp in components:
                score_record = comp_map.get(comp.id)
                if not score_record:
                    is_incomplete = True
                    continue

                if score_record.is_exempted:
                    exempted_weight += score_record.weight_snapshot
                    continue

                w_score = score_record.weighted_score
                if comp.category == AssessmentCategory.EXAMINATION:
                    exam_sum += w_score
                else:
                    ca_sum += w_score

            raw_total = ca_sum + exam_sum
            # If student had official exemptions, pro-rate remaining weights to 100%
            active_weight = Decimal('100.00') - exempted_weight
            if active_weight > Decimal('0.00') and exempted_weight > Decimal('0.00'):
                final_total = ((raw_total / active_weight) * Decimal('100.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            else:
                final_total = raw_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            grade_scale = resolve_grade_for_score(final_total, academic_session, class_obj.education_level)

            StudentResult.objects.update_or_create(
                student_enrollment=enrollment,
                academic_term=academic_term,
                subject=subject_obj,
                defaults={
                    'ca_total': ca_sum.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                    'exam_score': exam_sum.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                    'total_score': final_total,
                    'grade': grade_scale.grade_letter if grade_scale else None,
                    'grade_point': grade_scale.grade_point if grade_scale else Decimal('0.00'),
                    'remark': grade_scale.remark if grade_scale else '',
                    'is_incomplete': is_incomplete,
                    'status': ResultWorkflowStatus.UNDER_REVIEW,
                    'computed_at': now,
                }
            )

    # Step B: Compute Subject Statistics (Highest, Lowest, Average, and Subject Rank)
    for subject_obj in subjects_affected:
        subj_results = list(StudentResult.objects.filter(
            student_enrollment__in=enrollments,
            academic_term=academic_term,
            subject=subject_obj
        ))
        if not subj_results:
            continue

        stats = StudentResult.objects.filter(id__in=[r.id for r in subj_results]).aggregate(
            highest=Max('total_score'),
            lowest=Min('total_score'),
            average=Avg('total_score')
        )
        highest = (stats['highest'] or Decimal('0.00')).quantize(Decimal('0.01'))
        lowest = (stats['lowest'] or Decimal('0.00')).quantize(Decimal('0.01'))
        average = (stats['average'] or Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        StudentResult.objects.filter(id__in=[r.id for r in subj_results]).update(
            class_highest=highest,
            class_lowest=lowest,
            class_average=average
        )

        # Reload updated objects and assign subject rankings
        subj_results = list(StudentResult.objects.filter(id__in=[r.id for r in subj_results]))
        _assign_standard_rankings(subj_results, 'total_score', 'subject_position')

    # Step C: Compute StudentTermSummary for each student
    summaries = []
    total_students = len(enrollments)

    for enrollment in enrollments:
        student_subj_results = list(StudentResult.objects.filter(
            student_enrollment=enrollment,
            academic_term=academic_term
        ))
        subjects_count = len(student_subj_results)
        if subjects_count > 0:
            overall_total = sum((r.total_score for r in student_subj_results), Decimal('0.00')).quantize(Decimal('0.01'))
            overall_avg = (overall_total / Decimal(subjects_count)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            overall_gpa = (
                sum((r.grade_point for r in student_subj_results), Decimal('0.00')) / Decimal(subjects_count)
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            passed_count = sum(1 for r in student_subj_results if r.grade and r.grade.upper() != 'F' and r.total_score >= Decimal('40.00'))
        else:
            overall_total = Decimal('0.00')
            overall_avg = Decimal('0.00')
            overall_gpa = Decimal('0.00')
            passed_count = 0

        summary, _ = StudentTermSummary.objects.update_or_create(
            student_enrollment=enrollment,
            academic_term=academic_term,
            defaults={
                'subjects_offered': subjects_count,
                'subjects_passed': passed_count,
                'total_score': overall_total,
                'average_score': overall_avg,
                'gpa': overall_gpa,
                'total_students_in_class': total_students,
                'status': ResultWorkflowStatus.UNDER_REVIEW,
            }
        )
        summaries.append(summary)

    # Step D: Assign Class / Arm Positions based on average_score
    if class_arm:
        _assign_standard_rankings(summaries, 'average_score', 'arm_position')
    else:
        _assign_standard_rankings(summaries, 'average_score', 'class_position')

    ResultWorkflowAudit.objects.create(
        academic_session=academic_session,
        academic_term=academic_term,
        class_obj=class_obj,
        class_arm=class_arm,
        previous_status=ResultWorkflowStatus.SCORES_SUBMITTED,
        new_status=ResultWorkflowStatus.UNDER_REVIEW,
        performed_by=user,
        reason=f"Computed term results for {len(summaries)} student(s)."
    )

    log_audit_event(
        action=AuditAction.CREATE,
        category=AuditCategory.EXAMINATIONS,
        description=f"Computed term results for {len(enrollments)} student(s) in Class ID {class_id} for Term.",
        actor=user,
        metadata={
            # "term_id": str(term.id),
            "class_id": str(class_id),
            "computed_count": len(enrollments),
        },
    )

    return summaries


@transaction.atomic
def transition_class_result_workflow(academic_term_id, class_id, target_status, user, class_arm_id=None, reason=""):
    """
    Manages administrative state transitions for computed results:
    - UNDER_REVIEW -> APPROVED
    - APPROVED -> PUBLISHED
    - PUBLISHED -> LOCKED
    - APPROVED / PUBLISHED / LOCKED -> UNDER_REVIEW (Reopen; requires mandatory reason)
    """
    if not is_admin_user(user):
        raise PermissionDenied("Only authorized administrators can approve, publish, lock, or reopen results.")

    academic_term = AcademicTerm.objects.select_related('session').get(pk=academic_term_id)
    academic_session = academic_term.session
    class_obj = Class.objects.get(pk=class_id)
    class_arm = ClassArm.objects.get(pk=class_arm_id) if class_arm_id else None

    summaries_qs = StudentTermSummary.objects.filter(
        student_enrollment__academic_session=academic_session,
        student_enrollment__class_obj=class_obj,
        academic_term=academic_term,
    )
    results_qs = StudentResult.objects.filter(
        student_enrollment__academic_session=academic_session,
        student_enrollment__class_obj=class_obj,
        academic_term=academic_term,
    )
    if class_arm:
        summaries_qs = summaries_qs.filter(student_enrollment__class_arm=class_arm)
        results_qs = results_qs.filter(student_enrollment__class_arm=class_arm)

    if not summaries_qs.exists():
        raise ValidationError("No computed term summaries found for this class and term. Run result computation first.")

    current_status = summaries_qs.first().status
    now = timezone.now()

    valid_transitions = {
        ResultWorkflowStatus.UNDER_REVIEW: [ResultWorkflowStatus.APPROVED],
        ResultWorkflowStatus.APPROVED: [ResultWorkflowStatus.PUBLISHED, ResultWorkflowStatus.UNDER_REVIEW],
        ResultWorkflowStatus.PUBLISHED: [ResultWorkflowStatus.LOCKED, ResultWorkflowStatus.UNDER_REVIEW],
        ResultWorkflowStatus.LOCKED: [ResultWorkflowStatus.UNDER_REVIEW],
    }

    allowed_targets = valid_transitions.get(current_status, [])
    if target_status not in allowed_targets:
        raise ValidationError(
            f"Invalid workflow transition from '{current_status}' to '{target_status}'."
        )

    # Require explicit audit reason when reopening approved/published/locked results
    if target_status == ResultWorkflowStatus.UNDER_REVIEW and current_status in [
        ResultWorkflowStatus.APPROVED,
        ResultWorkflowStatus.PUBLISHED,
        ResultWorkflowStatus.LOCKED,
    ]:
        if not reason or not reason.strip():
            raise ValidationError({"reason": "A detailed audit reason is required when reopening approved or published results."})

    update_kwargs = {'status': target_status}
    if target_status == ResultWorkflowStatus.APPROVED:
        update_kwargs['approved_by'] = user
        update_kwargs['approved_at'] = now
    elif target_status == ResultWorkflowStatus.PUBLISHED:
        update_kwargs['published_by'] = user
        update_kwargs['published_at'] = now

    count = summaries_qs.update(**update_kwargs)
    results_qs.update(status=target_status)

    ResultWorkflowAudit.objects.create(
        academic_session=academic_session,
        academic_term=academic_term,
        class_obj=class_obj,
        class_arm=class_arm,
        previous_status=current_status,
        new_status=target_status,
        performed_by=user,
        reason=reason or f"Transitioned {count} student result(s) to {target_status}."
    )

    action_map = {
        ResultWorkflowStatus.APPROVED: AuditAction.APPROVE,
        ResultWorkflowStatus.PUBLISHED: AuditAction.PUBLISH,
        ResultWorkflowStatus.LOCKED: AuditAction.OTHER,
        ResultWorkflowStatus.UNDER_REVIEW: AuditAction.UNPUBLISH,
    }

    audit_action = action_map.get(target_status, AuditAction.UPDATE)

    log_audit_event(
        action=audit_action,
        category=AuditCategory.EXAMINATIONS,
        description=f"Transitioned {count} student result summary record(s) to status '{target_status}'. Reason: {reason or 'None'}",
        actor=user,
        metadata={
            "term_id": str(academic_term_id),
            "class_id": str(class_id),
            "target_status": target_status,
            "updated_count": count,
            "reason": reason,
        },
    )

    return count