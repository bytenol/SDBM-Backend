from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .permissions import (
    IsStaffPortalUser,
    IsStudentPortalUser,
    IsParentPortalUser,
)
from .serializers import (
    AccountMeUpdateSerializer,
    StaffSelfProfileSerializer,
    StudentSelfProfileSerializer,
    ParentProfileUpdateSerializer,
)
from .services import (
    build_consolidated_me_payload,
    get_staff_self_profile,
    get_student_self_profile,
    build_parent_self_profile_payload,
)


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