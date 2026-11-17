from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from drf_spectacular.utils import extend_schema
from .serializers import (
    LoginSerializer,
    LogoutSerializer,
    UserSerializer,
    ChangePasswordSerializer,
    AccountProvisioningSerializer
)

from .permissions import IsAdminOrSuperAdmin


class LoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    @extend_schema(
        summary="User Login",
        description="Authenticate using login_id (students/staff) or email (parents/admins). Returns JWT access/refresh tokens and user profile.",
        responses={200: UserSerializer}
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = serializer.validated_data['user']
            tokens = serializer.validated_data['tokens']
            user_data = UserSerializer(user).data
            return Response({
                "success": True,
                "message": "Login successful.",
                "data": {
                    "user": user_data,
                    "tokens": tokens
                }
            }, status=status.HTTP_200_OK)
        return Response({
            "success": False,
            "message": "Validation error.",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    @extend_schema(
        summary="User Logout",
        description="Blacklists the provided refresh token to terminate the session.",
        responses={200: {"description": "Successfully logged out."}}
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "success": True,
                "message": "Successfully logged out.",
                "data": None
            }, status=status.HTTP_200_OK)
        return Response({
            "success": False,
            "message": "Invalid token.",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    @extend_schema(
        summary="Get Current User Profile",
        description="Retrieves the authenticated user's profile details and assigned roles."
    )
    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(request.user)
        return Response({
            "success": True,
            "message": "User profile retrieved successfully.",
            "data": serializer.data
        }, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    @extend_schema(
        summary="Change Password",
        description="Allows an authenticated user to change their password securely."
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({
                "success": True,
                "message": "Password changed successfully.",
                "data": None
            }, status=status.HTTP_200_OK)
        return Response({
            "success": False,
            "message": "Password change failed.",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)



class AccountProvisioningView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    serializer_class = AccountProvisioningSerializer

    @extend_schema(
        summary="Provision User Account",
        description="Admin-only endpoint to create student, staff, parent, or admin accounts with auto-generated credentials.",
        responses={201: UserSerializer}
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            user, temp_password = serializer.save()
            user_data = UserSerializer(user).data
            return Response({
                "success": True,
                "message": f"Account successfully provisioned for {user.first_name} {user.last_name}.",
                "data": {
                    "user": user_data,
                    "temporary_password": temp_password
                }
            }, status=status.HTTP_201_CREATED)
        return Response({
            "success": False,
            "message": "Provisioning failed.",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)