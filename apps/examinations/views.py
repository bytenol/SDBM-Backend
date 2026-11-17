# apps/examinations/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiResponse,
)
from drf_spectacular.types import OpenApiTypes

from apps.accounts.permissions import IsAdminOrSuperAdmin
from apps.students.models import StudentGuardian
from apps.staff.models import TeacherAssignment
from .models import (
    Examination,
    AssessmentComponent,
    GradingScale,
    StudentScore,
    StudentResult,
    StudentTermSummary,
    ResultWorkflowAudit,
    ResultWorkflowStatus,
)
from .serializers import (
    ExaminationSerializer,
    AssessmentComponentSerializer,
    GradingScaleSerializer,
    StudentScoreSerializer,
    BulkScoreEntrySerializer,
    SubjectScoreSubmitSerializer,
    ClassResultComputeSerializer,
    ClassResultWorkflowSerializer,
    StudentResultSerializer,
    StudentTermSummarySerializer,
    ResultWorkflowAuditSerializer,
)
from .schemas import (
    BulkScoreEntryResponseSerializer,
    SubjectScoreSubmitResponseSerializer,
    ClassResultComputeResponseSerializer,
    ClassResultWorkflowResponseSerializer,
    ReportCardResponseSerializer,
)
from .filters import (
    ExaminationFilter,
    AssessmentComponentFilter,
    GradingScaleFilter,
    StudentScoreFilter,
    StudentResultFilter,
    StudentTermSummaryFilter,
)
from .permissions import (
    IsExamAdminOrReadOnly,
    IsTeacherOrExamAdmin,
    CanAccessResultRecord,
)
from .services import (
    record_bulk_student_scores,
    submit_subject_scores,
    compute_class_term_results,
    transition_class_result_workflow,
)
from .reports import build_report_card_payload, generate_report_card_pdf_response


@extend_schema_view(
    list=extend_schema(
        tags=['Examinations - Configuration'],
        summary='List examinations',
        description='Retrieve a paginated list of formal examination windows filtered by academic session, term, type, or status.',
    ),
    retrieve=extend_schema(
        tags=['Examinations - Configuration'],
        summary='Get examination details',
    ),
    create=extend_schema(
        tags=['Examinations - Configuration'],
        summary='Create an examination (Admin only)',
    ),
    update=extend_schema(
        tags=['Examinations - Configuration'],
        summary='Update an examination (Admin only)',
    ),
    partial_update=extend_schema(
        tags=['Examinations - Configuration'],
        summary='Partially update an examination (Admin only)',
    ),
    destroy=extend_schema(
        tags=['Examinations - Configuration'],
        summary='Delete an examination (Admin only)',
    ),
)
class ExaminationViewSet(viewsets.ModelViewSet):
    queryset = Examination.objects.select_related('academic_session', 'academic_term').prefetch_related('applicable_classes').all()
    serializer_class = ExaminationSerializer
    permission_classes = [permissions.IsAuthenticated, IsExamAdminOrReadOnly]
    filterset_class = ExaminationFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'instructions']
    ordering_fields = ['start_date', 'created_at']


@extend_schema_view(
    list=extend_schema(
        tags=['Examinations - Configuration'],
        summary='List assessment components',
        description='Retrieve configured assessment components (e.g. CA1, CA2, Assignment, Exam) and their maximum scores and weightings.',
    ),
    retrieve=extend_schema(
        tags=['Examinations - Configuration'],
        summary='Get assessment component details',
    ),
    create=extend_schema(
        tags=['Examinations - Configuration'],
        summary='Create an assessment component (Admin only)',
        description='Creates an assessment component. Validates that active component weights within the same session/term/class scope do not exceed 100%.',
    ),
    update=extend_schema(
        tags=['Examinations - Configuration'],
        summary='Update an assessment component (Admin only)',
    ),
    partial_update=extend_schema(
        tags=['Examinations - Configuration'],
        summary='Partially update an assessment component (Admin only)',
    ),
    destroy=extend_schema(
        tags=['Examinations - Configuration'],
        summary='Delete an assessment component (Admin only)',
    ),
)
class AssessmentComponentViewSet(viewsets.ModelViewSet):
    queryset = AssessmentComponent.objects.select_related('academic_session', 'academic_term', 'class_obj').all()
    serializer_class = AssessmentComponentSerializer
    permission_classes = [permissions.IsAuthenticated, IsExamAdminOrReadOnly]
    filterset_class = AssessmentComponentFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'code']
    ordering_fields = ['display_order', 'weight_percentage']


@extend_schema_view(
    list=extend_schema(
        tags=['Examinations - Configuration'],
        summary='List grading scales',
        description='Retrieve active or historical grading scales (score boundaries, letter grades, grade points, and remarks).',
    ),
    retrieve=extend_schema(
        tags=['Examinations - Configuration'],
        summary='Get grading scale details',
    ),
    create=extend_schema(
        tags=['Examinations - Configuration'],
        summary='Create a grading scale boundary (Admin only)',
        description='Creates a grade boundary and validates that score ranges do not overlap within the same session and education level.',
    ),
    update=extend_schema(
        tags=['Examinations - Configuration'],
        summary='Update a grading scale boundary (Admin only)',
    ),
    partial_update=extend_schema(
        tags=['Examinations - Configuration'],
        summary='Partially update a grading scale boundary (Admin only)',
    ),
    destroy=extend_schema(
        tags=['Examinations - Configuration'],
        summary='Delete a grading scale boundary (Admin only)',
    ),
)
class GradingScaleViewSet(viewsets.ModelViewSet):
    queryset = GradingScale.objects.select_related('academic_session').all()
    serializer_class = GradingScaleSerializer
    permission_classes = [permissions.IsAuthenticated, IsExamAdminOrReadOnly]
    filterset_class = GradingScaleFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['grade_letter', 'remark']
    ordering_fields = ['min_score', 'grade_point']


@extend_schema_view(
    list=extend_schema(
        tags=['Examinations - Score Entry'],
        summary='List student raw assessment scores',
        description='Admins view all scores; Teachers automatically view scores scoped to their active TeacherAssignments.',
    ),
    retrieve=extend_schema(
        tags=['Examinations - Score Entry'],
        summary='Get individual student score record',
    ),
    create=extend_schema(
        tags=['Examinations - Score Entry'],
        summary='Create a single student score record',
    ),
    update=extend_schema(
        tags=['Examinations - Score Entry'],
        summary='Update a single student score record',
    ),
    partial_update=extend_schema(
        tags=['Examinations - Score Entry'],
        summary='Partially update a single student score record',
    ),
    destroy=extend_schema(
        tags=['Examinations - Score Entry'],
        summary='Delete a student score record',
    ),
)
class StudentScoreViewSet(viewsets.ModelViewSet):
    queryset = StudentScore.objects.select_related(
        'student_enrollment__student__user',
        'student_enrollment__class_obj',
        'student_enrollment__class_arm',
        'academic_term',
        'subject',
        'assessment_component',
    ).all()
    serializer_class = StudentScoreSerializer
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrExamAdmin]
    filterset_class = StudentScoreFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = [
        'student_enrollment__student__first_name',
        'student_enrollment__student__last_name',
        'student_enrollment__student__user__login_id',
        'subject__name',
    ]
    ordering_fields = ['score', 'created_at']

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.is_superuser or user.roles.filter(name__in=['SUPER_ADMIN', 'ADMIN']).exists():
            return qs
        if hasattr(user, 'staff_profile'):
            assigned = TeacherAssignment.objects.filter(staff=user.staff_profile, is_active=True)
            class_ids = assigned.values_list('class_obj_id', flat=True)
            subject_ids = assigned.values_list('subject_id', flat=True)
            return qs.filter(
                student_enrollment__class_obj_id__in=class_ids,
                subject_id__in=subject_ids
            )
        return qs.none()

    @extend_schema(
        tags=['Examinations - Score Entry'],
        summary='Bulk enter or update raw student scores',
        description=(
            'Atomically records or updates raw marks for a class, subject, and assessment component. '
            'Verifies TeacherAssignment authority, checks maximum score bounds, and snapshots component weights.'
        ),
        request=BulkScoreEntrySerializer,
        responses={
            200: BulkScoreEntryResponseSerializer,
            400: OpenApiResponse(description='Validation error (score exceeds max, invalid enrollment, or locked result).'),
            403: OpenApiResponse(description='Permission denied (teacher not assigned to subject/class).'),
        },
    )
    @action(detail=False, methods=['post'], url_path='bulk-entry')
    def bulk_entry(self, request):
        serializer = BulkScoreEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        saved_scores = record_bulk_student_scores(serializer.validated_data, request.user)
        return Response({
            "success": True,
            "message": f"Successfully saved {len(saved_scores)} student score record(s).",
            "data": StudentScoreSerializer(saved_scores, many=True).data,
        }, status=status.HTTP_200_OK)

    @extend_schema(
        tags=['Examinations - Score Entry'],
        summary='Submit subject scores for administrative review',
        description='Transitions all DRAFT scores for the specified term, class, and subject to SUBMITTED and records a workflow audit entry.',
        request=SubjectScoreSubmitSerializer,
        responses={
            200: SubjectScoreSubmitResponseSerializer,
            400: OpenApiResponse(description='No draft scores found for the specified class and subject.'),
            403: OpenApiResponse(description='User is not authorized for this subject/class.'),
        },
    )
    @action(detail=False, methods=['post'], url_path='submit')
    def submit_scores(self, request):
        serializer = SubjectScoreSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        updated_count = submit_subject_scores(
            academic_term_id=data['academic_term'],
            class_id=data['class_obj'],
            subject_id=data['subject'],
            user=request.user,
            class_arm_id=data.get('class_arm'),
        )
        return Response({
            "success": True,
            "message": f"Successfully submitted {updated_count} score record(s) for review.",
            "data": {"submitted_count": updated_count},
        }, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(
        tags=['Examinations - Results & Report Cards'],
        summary='List computed subject-level results',
        description=(
            'Returns computed subject results (CA total, exam score, total score, grade, position, and class stats). '
            'Students and Parents only see results in PUBLISHED or LOCKED status.'
        ),
    ),
    retrieve=extend_schema(
        tags=['Examinations - Results & Report Cards'],
        summary='Get a single subject-level result record',
    ),
)
class StudentResultViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StudentResult.objects.select_related(
        'student_enrollment__student__user',
        'student_enrollment__class_obj',
        'student_enrollment__class_arm',
        'academic_term',
        'subject',
    ).all()
    serializer_class = StudentResultSerializer
    permission_classes = [permissions.IsAuthenticated, CanAccessResultRecord]
    filterset_class = StudentResultFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = [
        'student_enrollment__student__first_name',
        'student_enrollment__student__last_name',
        'student_enrollment__student__user__login_id',
        'subject__name',
    ]
    ordering_fields = ['total_score', 'subject_position']

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        published_states = [ResultWorkflowStatus.PUBLISHED, ResultWorkflowStatus.LOCKED]

        if user.is_superuser or user.roles.filter(name__in=['SUPER_ADMIN', 'ADMIN']).exists():
            return qs

        if user.roles.filter(name='STAFF').exists() and hasattr(user, 'staff_profile'):
            assigned_classes = TeacherAssignment.objects.filter(
                staff=user.staff_profile, is_active=True
            ).values_list('class_obj_id', flat=True)
            return qs.filter(student_enrollment__class_obj_id__in=assigned_classes)

        if user.roles.filter(name='STUDENT').exists() and hasattr(user, 'student_profile'):
            return qs.filter(
                student_enrollment__student=user.student_profile,
                status__in=published_states
            )

        if user.roles.filter(name='PARENT').exists():
            linked_students = StudentGuardian.objects.filter(guardian=user).values_list('student_id', flat=True)
            return qs.filter(
                student_enrollment__student_id__in=linked_students,
                status__in=published_states
            )

        return qs.none()


@extend_schema_view(
    list=extend_schema(
        tags=['Examinations - Results & Report Cards'],
        summary='List student term performance summaries',
        description=(
            'Returns term performance master records (total score, average, GPA, class/arm position, and workflow status). '
            'Students and Parents only receive their own or linked children\'s PUBLISHED/LOCKED summaries.'
        ),
    ),
    retrieve=extend_schema(
        tags=['Examinations - Results & Report Cards'],
        summary='Get a student term performance summary',
    ),
    update=extend_schema(
        tags=['Examinations - Results & Report Cards'],
        summary='Update teacher/principal remarks on a term summary',
    ),
    partial_update=extend_schema(
        tags=['Examinations - Results & Report Cards'],
        summary='Partially update teacher/principal remarks on a term summary',
    ),
)
class StudentTermSummaryViewSet(viewsets.ModelViewSet):
    queryset = StudentTermSummary.objects.select_related(
        'student_enrollment__student__user',
        'student_enrollment__academic_session',
        'student_enrollment__class_obj',
        'student_enrollment__class_arm',
        'academic_term',
    ).all()
    serializer_class = StudentTermSummarySerializer
    permission_classes = [permissions.IsAuthenticated, CanAccessResultRecord]
    filterset_class = StudentTermSummaryFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = [
        'student_enrollment__student__first_name',
        'student_enrollment__student__last_name',
        'student_enrollment__student__user__login_id',
    ]
    ordering_fields = ['average_score', 'class_position', 'arm_position']

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        published_states = [ResultWorkflowStatus.PUBLISHED, ResultWorkflowStatus.LOCKED]

        if user.is_superuser or user.roles.filter(name__in=['SUPER_ADMIN', 'ADMIN']).exists():
            return qs

        if user.roles.filter(name='STAFF').exists() and hasattr(user, 'staff_profile'):
            assigned_classes = TeacherAssignment.objects.filter(
                staff=user.staff_profile, is_active=True
            ).values_list('class_obj_id', flat=True)
            return qs.filter(student_enrollment__class_obj_id__in=assigned_classes)

        if user.roles.filter(name='STUDENT').exists() and hasattr(user, 'student_profile'):
            return qs.filter(
                student_enrollment__student=user.student_profile,
                status__in=published_states
            )

        if user.roles.filter(name='PARENT').exists():
            linked_students = StudentGuardian.objects.filter(guardian=user).values_list('student_id', flat=True)
            return qs.filter(
                student_enrollment__student_id__in=linked_students,
                status__in=published_states
            )

        return qs.none()

    @extend_schema(
        tags=['Examinations - Computation & Workflow'],
        summary='Compute class term results, grades, and rankings (Admin only)',
        description=(
            'Executes the backend result computation engine for a class and term: normalizes component scores, '
            'applies grading scales, computes subject highest/lowest/average statistics, and calculates standard competition rankings.'
        ),
        request=ClassResultComputeSerializer,
        responses={
            200: ClassResultComputeResponseSerializer,
            400: OpenApiResponse(description='Component weights do not equal 100%, or results are already locked/published.'),
            403: OpenApiResponse(description='Only administrators can trigger class result computation.'),
        },
    )
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsAdminOrSuperAdmin])
    def compute(self, request):
        serializer = ClassResultComputeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        summaries = compute_class_term_results(
            academic_term_id=data['academic_term'],
            class_id=data['class_obj'],
            user=request.user,
            class_arm_id=data.get('class_arm'),
        )
        return Response({
            "success": True,
            "message": f"Successfully computed term results for {len(summaries)} student(s).",
            "data": {"computed_students_count": len(summaries)},
        }, status=status.HTTP_200_OK)

    @extend_schema(
        tags=['Examinations - Computation & Workflow'],
        summary='Transition class result workflow status (Admin only)',
        description=(
            'Transitions computed class results across UNDER_REVIEW -> APPROVED -> PUBLISHED -> LOCKED. '
            'Reopening APPROVED, PUBLISHED, or LOCKED results back to UNDER_REVIEW requires a mandatory audit reason.'
        ),
        request=ClassResultWorkflowSerializer,
        responses={
            200: ClassResultWorkflowResponseSerializer,
            400: OpenApiResponse(description='Invalid state transition or missing mandatory reason when reopening.'),
            403: OpenApiResponse(description='Only administrators can perform workflow transitions.'),
        },
    )
    @action(detail=False, methods=['post'], url_path='workflow-transition', permission_classes=[permissions.IsAuthenticated, IsAdminOrSuperAdmin])
    def workflow_transition(self, request):
        serializer = ClassResultWorkflowSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        count = transition_class_result_workflow(
            academic_term_id=data['academic_term'],
            class_id=data['class_obj'],
            target_status=data['target_status'],
            user=request.user,
            class_arm_id=data.get('class_arm'),
            reason=data.get('reason', ''),
        )
        return Response({
            "success": True,
            "message": f"Successfully transitioned {count} result summary record(s) to '{data['target_status']}'.",
            "data": {
                "updated_count": count,
                "new_status": data['target_status'],
            },
        }, status=status.HTTP_200_OK)

    @extend_schema(
        tags=['Examinations - Results & Report Cards'],
        summary='Retrieve or download student term report card (JSON or PDF)',
        description=(
            'Returns the complete student report card payload (including admission number via User.login_id, '
            'subject breakdowns, grades, and positions). Pass `?export=pdf` to download a printable PDF report card.'
        ),
        parameters=[
            OpenApiParameter(
                name='export',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                enum=['pdf'],
                description='Set to `pdf` to download the report card as a printable PDF document.',
            ),
        ],
        responses={
            200: ReportCardResponseSerializer,
            403: OpenApiResponse(description='Permission denied (unpublished result or unlinked student/guardian).'),
            404: OpenApiResponse(description='Term summary not found.'),
        },
    )
    @action(detail=True, methods=['get'], url_path='report-card')
    def report_card(self, request, pk=None):
        summary = self.get_object()
        payload = build_report_card_payload(summary)
        if request.query_params.get('export') == 'pdf':
            return generate_report_card_pdf_response(payload)
        return Response({
            "success": True,
            "data": payload,
        }, status=status.HTTP_200_OK)



@extend_schema_view(
    list=extend_schema(
        tags=['Examinations - Computation & Workflow'],
        summary='List result workflow audit logs (Admin only)',
        description='Immutable audit history of all score submissions, result computations, approvals, publications, and reopenings.',
    ),
    retrieve=extend_schema(
        tags=['Examinations - Computation & Workflow'],
        summary='Get result workflow audit log details (Admin only)',
    ),
)
class ResultWorkflowAuditViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ResultWorkflowAudit.objects.select_related(
        'academic_session', 'academic_term', 'class_obj', 'class_arm', 'subject', 'performed_by'
    ).all()
    serializer_class = ResultWorkflowAuditSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrSuperAdmin]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['academic_session', 'academic_term', 'class_obj', 'subject', 'new_status']
    ordering_fields = ['created_at']