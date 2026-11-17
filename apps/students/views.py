# apps/students/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.accounts.permissions import IsAdminOrSuperAdmin
from .models import Student, StudentGuardian, StudentEnrollment, StudentDocument
from .serializers import (
    StudentSerializer,
    StudentProvisioningSerializer,
    StudentDocumentSerializer,
    StudentPromotionSerializer
)
from .filters import StudentFilter
from .permissions import IsStudentAdminOrAuthorizedStaff

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.select_related('user').prefetch_related(
        'guardians__guardian', 'enrollments__academic_session',
        'enrollments__class_obj', 'enrollments__class_arm', 'documents'
    ).all()
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudentAdminOrAuthorizedStaff]
    filterset_class = StudentFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['first_name', 'last_name', 'user__login_id', 'user__email']
    ordering_fields = ['last_name', 'admission_date', 'created_at']


    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.is_superuser or user.roles.filter(name__in=['ADMIN', 'SUPER_ADMIN', 'STAFF']).exists():
            return qs
        if user.roles.filter(name='STUDENT').exists() and hasattr(user, 'student_profile'):
            return qs.filter(pk=user.student_profile.pk)
        if user.roles.filter(name='PARENT').exists():
            return qs.filter(guardians__guardian=user)
        return qs.none()


    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsAdminOrSuperAdmin])
    def provision(self, request):
        serializer = StudentProvisioningSerializer(data=request.data)
        if serializer.is_valid():
            student, temp_password = serializer.save(admin_user=request.user)
            student_data = StudentSerializer(student, context={'request': request}).data
            return Response({
                "success": True,
                "message": f"Student provisioned successfully with admission number {student.user.login_id}.",
                "data": {
                    "student": student_data,
                    "temporary_password": temp_password
                }
            }, status=status.HTTP_201_CREATED)
        return Response({
            "success": False,
            "message": "Student provisioning failed.",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsAdminOrSuperAdmin])
    def upload_document(self, request, pk=None):
        student = self.get_object()
        serializer = StudentDocumentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(student=student, uploaded_by=request.user)
            return Response({
                "success": True,
                "message": "Document uploaded successfully.",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response({
            "success": False,
            "message": "Document upload failed.",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsAdminOrSuperAdmin])
    def promote(self, request):
        """
        Endpoint for individual or bulk student promotion across academic sessions.
        Requires ADMIN or SUPER_ADMIN role.
        """
        serializer = StudentPromotionSerializer(data=request.data)
        if serializer.is_valid():
            log, count = serializer.save(admin_user=request.user)
            return Response({
                "success": True,
                "message": f"Successfully promoted {count} student(s) to the new academic session.",
                "data": {
                    "promoted_count": count,
                    "log_id": str(log.id),
                    "source_session": str(log.source_session.name),
                    "destination_session": str(log.destination_session.name),
                    "destination_class": str(log.destination_class.name)
                }
            }, status=status.HTTP_200_OK)
        return Response({
            "success": False,
            "message": "Student promotion failed.",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)



class StudentDocumentViewSet(viewsets.ModelViewSet):
    queryset = StudentDocument.objects.select_related('student', 'uploaded_by').all()
    serializer_class = StudentDocumentSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudentAdminOrAuthorizedStaff]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.is_superuser or user.roles.filter(name__in=['ADMIN', 'SUPER_ADMIN', 'STAFF']).exists():
            return qs
        if user.roles.filter(name='STUDENT').exists() and hasattr(user, 'student_profile'):
            return qs.filter(student=user.student_profile)
        if user.roles.filter(name='PARENT').exists():
            return qs.filter(student__guardians__guardian=user)
        return qs.none()