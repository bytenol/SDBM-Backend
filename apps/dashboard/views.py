from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from apps.dashboard.services.academic_services import build_academic_overview_payload, build_enrollment_analytics_payload, build_result_analytics_payload, build_staff_analytics_payload
from apps.dashboard.services.admin_services import build_admin_dashboard_payload
from apps.dashboard.services.guardian_services import build_parent_dashboard_payload
from apps.dashboard.services.staff_services import build_staff_dashboard_payload
from apps.dashboard.services.student_services import build_student_dashboard_payload
from .permissions import (
    IsAdminPortalUser,
    IsStaffPortalUser,
    IsStudentPortalUser,
    IsParentPortalUser,
)
from .serializers import (
    AccountMeUpdateSerializer,
    StaffSelfProfileSerializer,
    StudentSelfProfileSerializer,
    ParentProfileUpdateSerializer,
    DashboardContextFilterSerializer,
)
from .services.dashboard_services import (
    build_consolidated_me_payload,
    get_staff_self_profile,
    get_student_self_profile,
    build_parent_self_profile_payload
)


from .cache import get_or_compute_admin_aggregate


class AcademicOverviewAPIView(APIView):
    """
    GET /api/v1/dashboard/academic-overview/
    Returns the current academic session, current term, available sessions/terms,
    classes, class arms, subjects, and class-subject mappings.
    Automatically scopes class/subject lists based on the authenticated user's role.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['Portal - Academic Overview & Analytics'],
        summary='Get role-scoped Academic Overview (sessions, terms, classes, arms, subjects)',
        description=(
            'Reuses Phase 3 academic models to return the current session/term, available sessions, '
            'classes, class arms, subjects, and class-subject relationships. '
            'Admins and Staff see all active classes/subjects; Students and Parents see classes/subjects '
            'scoped to their active or linked enrollments.'
        ),
        parameters=[
            OpenApiParameter(
                name='session_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Optional AcademicSession UUID override.',
            ),
        ],
        responses={200: OpenApiResponse(description='Role-scoped academic overview payload.')},
    )
    def get(self, request):
        filter_serializer = DashboardContextFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)

        payload = build_academic_overview_payload(
            user=request.user,
            session_id=filter_serializer.validated_data.get('session_id'),
        )
        return Response({
            "success": True,
            "data": payload,
        }, status=status.HTTP_200_OK)


class EnrollmentAnalyticsAPIView(APIView):
    """
    GET /api/v1/dashboard/analytics/enrollments/
    Returns detailed student enrollment analytics (by status, gender, education level,
    class, class arm, and historical session trends). Admin only.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminPortalUser]

    @extend_schema(
        tags=['Portal - Academic Overview & Analytics'],
        summary='Get deep Student Enrollment Analytics (Admin only)',
        parameters=[
            OpenApiParameter(
                name='session_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Optional AcademicSession UUID override.',
            ),
        ],
        responses={
            200: OpenApiResponse(description='Enrollment analytics payload.'),
            403: OpenApiResponse(description='Forbidden — requires ADMIN or SUPER_ADMIN role.'),
        },
    )


    def get(self, request):
        filter_serializer = DashboardContextFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)
        v_data = filter_serializer.validated_data

        payload = get_or_compute_admin_aggregate(
            namespace="analytics_enrollments",
            params={"session_id": v_data.get("session_id")},
            builder_fn=lambda: build_enrollment_analytics_payload(
                session_id=v_data.get("session_id"),
            ),
            force_refresh=v_data.get("refresh", False),
        )
        return Response({"success": True, "data": payload}, status=status.HTTP_200_OK)



class StaffAnalyticsAPIView(APIView):
    """
    GET /api/v1/dashboard/analytics/staff/
    Returns detailed staff & HR analytics (demographics, employment status,
    employment types, designation categories, department headcounts, and teaching workload). Admin only.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminPortalUser]

    @extend_schema(
        tags=['Portal - Academic Overview & Analytics'],
        summary='Get deep Staff & HR Analytics (Admin only)',
        parameters=[
            OpenApiParameter(
                name='session_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Optional AcademicSession UUID for teaching workload aggregation.',
            ),
        ],
        responses={
            200: OpenApiResponse(description='Staff analytics payload.'),
            403: OpenApiResponse(description='Forbidden — requires ADMIN or SUPER_ADMIN role.'),
        },
    )


    def get(self, request):
        filter_serializer = DashboardContextFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)
        v_data = filter_serializer.validated_data

        payload = get_or_compute_admin_aggregate(
            namespace="analytics_staff",
            params={"session_id": v_data.get("session_id")},
            builder_fn=lambda: build_staff_analytics_payload(
                session_id=v_data.get("session_id"),
            ),
            force_refresh=v_data.get("refresh", False),
        )
        return Response({"success": True, "data": payload}, status=status.HTTP_200_OK)


class ResultAnalyticsAPIView(APIView):
    """
    GET /api/v1/dashboard/analytics/results/
    Returns term-wide examination and result analytics (workflow pipeline counts,
    class performance comparisons, grade distributions, and subject pass rates). Admin only.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminPortalUser]

    @extend_schema(
        tags=['Portal - Academic Overview & Analytics'],
        summary='Get deep Examination & Result Analytics (Admin only)',
        parameters=[
            OpenApiParameter(
                name='session_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Optional AcademicSession UUID override.',
            ),
            OpenApiParameter(
                name='term_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Optional AcademicTerm UUID override.',
            ),
            OpenApiParameter(
                name='class_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Optional Class UUID to scope result analytics to a single class.',
            ),
        ],
        responses={
            200: OpenApiResponse(description='Result analytics payload.'),
            403: OpenApiResponse(description='Forbidden — requires ADMIN or SUPER_ADMIN role.'),
        },
    )


    def get(self, request):
        filter_serializer = DashboardContextFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)
        v_data = filter_serializer.validated_data

        payload = get_or_compute_admin_aggregate(
            namespace="analytics_results",
            params={
                "session_id": v_data.get("session_id"),
                "term_id": v_data.get("term_id"),
                "class_id": v_data.get("class_id"),
            },
            builder_fn=lambda: build_result_analytics_payload(
                session_id=v_data.get("session_id"),
                term_id=v_data.get("term_id"),
                class_id=v_data.get("class_id"),
            ),
            force_refresh=v_data.get("refresh", False),
        )
        return Response({"success": True, "data": payload}, status=status.HTTP_200_OK)



class ParentDashboardAPIView(APIView):
    """
    GET /api/v1/dashboard/parent/
    Returns the authenticated parent/guardian's profile, linked children cards,
    each child's admission number (User.login_id), current class/arm enrollment,
    assigned class teacher, and published examination results.
    Enforces strict guardian linkage and prevents IDOR access to unrelated students.
    """
    permission_classes = [permissions.IsAuthenticated, IsParentPortalUser]

    @extend_schema(
        tags=['Portal - Role Dashboards'],
        summary='Get authenticated Parent Dashboard overview (multi-child support)',
        description=(
            'Returns all children linked to the authenticated parent via `StudentGuardian`, including '
            'each child\'s admission number (`User.login_id`), current session enrollment, class teacher, '
            'and strictly PUBLISHED/LOCKED term results. Optionally pass `student_id` to filter to one linked child.'
        ),
        parameters=[
            OpenApiParameter(
                name='student_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Optional Student UUID to filter dashboard data to a single linked child (verified against StudentGuardian).',
            ),
            OpenApiParameter(
                name='session_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Optional AcademicSession UUID override.',
            ),
            OpenApiParameter(
                name='term_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Optional AcademicTerm UUID override.',
            ),
        ],
        responses={
            200: OpenApiResponse(description='Parent dashboard payload with linked children cards.'),
            403: OpenApiResponse(description='Forbidden — user is not a parent or requested an unlinked student_id.'),
        },
    )
    def get(self, request):
        filter_serializer = DashboardContextFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)

        payload = build_parent_dashboard_payload(
            user=request.user,
            session_id=filter_serializer.validated_data.get('session_id'),
            term_id=filter_serializer.validated_data.get('term_id'),
            student_id=filter_serializer.validated_data.get('student_id'),
        )
        return Response({
            "success": True,
            "data": payload,
        }, status=status.HTTP_200_OK)


class StudentDashboardAPIView(APIView):
    """
    GET /api/v1/dashboard/student/
    Returns the authenticated student's profile, admission number (User.login_id),
    current class/arm placement, assigned subjects and teachers, published examination
    results, and academic enrollment history.
    Strictly scoped to request.user.student_profile.
    """
    permission_classes = [permissions.IsAuthenticated, IsStudentPortalUser]

    @extend_schema(
        tags=['Portal - Role Dashboards'],
        summary='Get authenticated Student Dashboard overview',
        description=(
            'Returns the authenticated student\'s profile, admission number (`User.login_id`), '
            'current enrollment, class teacher, offered subjects, enrollment history, and '
            'strictly PUBLISHED/LOCKED examination results.'
        ),
        parameters=[
            OpenApiParameter(
                name='session_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Optional AcademicSession UUID override.',
            ),
            OpenApiParameter(
                name='term_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Optional AcademicTerm UUID override.',
            ),
        ],
        responses={
            200: OpenApiResponse(description='Student dashboard payload.'),
            403: OpenApiResponse(description='Forbidden — requires STUDENT role with an active student_profile.'),
        },
    )
    def get(self, request):
        filter_serializer = DashboardContextFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)

        payload = build_student_dashboard_payload(
            user=request.user,
            session_id=filter_serializer.validated_data.get('session_id'),
            term_id=filter_serializer.validated_data.get('term_id'),
        )
        return Response({
            "success": True,
            "data": payload,
        }, status=status.HTTP_200_OK)



class StaffDashboardAPIView(APIView):
    """
    GET /api/v1/dashboard/staff/
    Returns the authenticated staff member's profile, employment details, department,
    designation, assigned classes and subjects, authorized students, and score submission progress.
    Supports both teaching and non-teaching staff.
    """
    permission_classes = [permissions.IsAuthenticated, IsStaffPortalUser]

    @extend_schema(
        tags=['Portal - Role Dashboards'],
        summary='Get authenticated Staff Dashboard overview',
        description=(
            'Returns employment details, department/designation, active session teaching assignments, '
            'authorized class student counts, and term score submission progress for the authenticated staff member. '
            'Non-teaching staff receive their full employment and school calendar context with empty teaching lists.'
        ),
        parameters=[
            OpenApiParameter(
                name='session_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Optional AcademicSession UUID override (defaults to current session).',
            ),
            OpenApiParameter(
                name='term_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Optional AcademicTerm UUID override (defaults to current term).',
            ),
        ],
        responses={
            200: OpenApiResponse(description='Staff dashboard payload.'),
            403: OpenApiResponse(description='Forbidden — requires STAFF role with an active staff_profile.'),
        },
    )
    def get(self, request):
        filter_serializer = DashboardContextFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)

        payload = build_staff_dashboard_payload(
            user=request.user,
            session_id=filter_serializer.validated_data.get('session_id'),
            term_id=filter_serializer.validated_data.get('term_id'),
        )
        return Response({
            "success": True,
            "data": payload,
        }, status=status.HTTP_200_OK)



class AdminDashboardAPIView(APIView):
    """
    GET /api/v1/dashboard/admin/
    Returns consolidated school-wide KPIs, class/arm enrollment distributions,
    department staff breakdowns, result workflow pipeline counts, and recent onboarding records.
    Restricted strictly to SUPER_ADMIN and ADMIN roles.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminPortalUser]

    @extend_schema(
        tags=['Portal - Role Dashboards'],
        summary='Get Administrator Dashboard overview & KPIs (Admin only)',
        description=(
            'Aggregates school-wide metrics for students, staff, classes, subjects, '
            'enrollment distributions, department headcounts, and result approval workflows. '
            'Optionally pass `session_id` and `term_id` to inspect historical academic periods.'
        ),
        parameters=[
            OpenApiParameter(
                name='session_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Optional AcademicSession UUID override (defaults to current session in SchoolSettings).',
            ),
            OpenApiParameter(
                name='term_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Optional AcademicTerm UUID override (defaults to current term in SchoolSettings).',
            ),
        ],
        responses={
            200: OpenApiResponse(description='Consolidated administrator dashboard payload.'),
            403: OpenApiResponse(description='Forbidden — requires ADMIN or SUPER_ADMIN role.'),
        },
    )


    def get(self, request):
        filter_serializer = DashboardContextFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)
        v_data = filter_serializer.validated_data

        payload = get_or_compute_admin_aggregate(
            namespace="admin_overview",
            params={"session_id": v_data.get("session_id"), "term_id": v_data.get("term_id")},
            builder_fn=lambda: build_admin_dashboard_payload(
                session_id=v_data.get("session_id"),
                term_id=v_data.get("term_id"),
            ),
            force_refresh=v_data.get("refresh", False),
        )
        return Response({"success": True, "data": payload}, status=status.HTTP_200_OK)



class ProfileMeAPIView(APIView):
    """
    GET, PATCH /api/v1/profile/me/
    Returns the authenticated user's account details, assigned roles, available portals,
    role-specific summary cards, and active school session/term context.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['Portal - Consolidated Profiles'],
        summary='Get current authenticated user profile & portal context',
        description='Returns account identity (including User.login_id), active roles, primary portal routing target, and role-specific profile summaries.',
    )
    def get(self, request):
        payload = build_consolidated_me_payload(request.user)
        return Response({
            "success": True,
            "data": payload,
        }, status=status.HTTP_200_OK)

    @extend_schema(
        tags=['Portal - Consolidated Profiles'],
        summary='Update current user basic account details',
        request=AccountMeUpdateSerializer,
    )
    def patch(self, request):
        serializer = AccountMeUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        payload = build_consolidated_me_payload(request.user)
        return Response({
            "success": True,
            "message": "Account profile updated successfully.",
            "data": payload,
        }, status=status.HTTP_200_OK)


class StaffSelfProfileAPIView(APIView):
    """
    GET, PATCH /api/v1/profile/staff/
    Returns or updates the authenticated staff member's own profile.
    """
    permission_classes = [permissions.IsAuthenticated, IsStaffPortalUser]

    @extend_schema(
        tags=['Portal - Consolidated Profiles'],
        summary='Get authenticated staff member profile',
        responses={
            200: StaffSelfProfileSerializer,
            403: OpenApiResponse(description='User does not hold an active staff profile.'),
        },
    )
    def get(self, request):
        staff = get_staff_self_profile(request.user)
        serializer = StaffSelfProfileSerializer(staff, context={'request': request})
        return Response({
            "success": True,
            "data": serializer.data,
        }, status=status.HTTP_200_OK)

    @extend_schema(
        tags=['Portal - Consolidated Profiles'],
        summary='Update staff self-service contact & emergency details',
        description='Allows a staff member to update their phone_number, residential_address, emergency contact fields, passport_photograph, and bio. Employment records and designations cannot be self-modified.',
        request=StaffSelfProfileSerializer,
        responses={200: StaffSelfProfileSerializer},
    )
    def patch(self, request):
        staff = get_staff_self_profile(request.user)
        serializer = StaffSelfProfileSerializer(
            staff,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            "success": True,
            "message": "Staff profile updated successfully.",
            "data": serializer.data,
        }, status=status.HTTP_200_OK)


class StudentSelfProfileAPIView(APIView):
    """
    GET /api/v1/profile/student/
    Returns the authenticated student's profile, admission number (User.login_id),
    enrollment history, and linked guardians.
    """
    permission_classes = [permissions.IsAuthenticated, IsStudentPortalUser]

    @extend_schema(
        tags=['Portal - Consolidated Profiles'],
        summary='Get authenticated student profile & enrollment history',
        responses={
            200: StudentSelfProfileSerializer,
            403: OpenApiResponse(description='User does not hold an active student profile.'),
        },
    )
    def get(self, request):
        student = get_student_self_profile(request.user)
        serializer = StudentSelfProfileSerializer(student, context={'request': request})
        return Response({
            "success": True,
            "data": serializer.data,
        }, status=status.HTTP_200_OK)


class ParentSelfProfileAPIView(APIView):
    """
    GET, PATCH /api/v1/profile/parent/
    Returns the authenticated parent/guardian's profile and all linked children.
    """
    permission_classes = [permissions.IsAuthenticated, IsParentPortalUser]

    @extend_schema(
        tags=['Portal - Consolidated Profiles'],
        summary='Get authenticated parent profile & linked children',
    )
    def get(self, request):
        payload = build_parent_self_profile_payload(request.user)
        return Response({
            "success": True,
            "data": payload,
        }, status=status.HTTP_200_OK)

    @extend_schema(
        tags=['Portal - Consolidated Profiles'],
        summary='Update authenticated parent basic contact details',
        request=ParentProfileUpdateSerializer,
    )
    def patch(self, request):
        serializer = ParentProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        payload = build_parent_self_profile_payload(request.user)
        return Response({
            "success": True,
            "message": "Parent profile updated successfully.",
            "data": payload,
        }, status=status.HTTP_200_OK)