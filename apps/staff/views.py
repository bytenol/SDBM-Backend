from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter


from apps.accounts.permissions import IsAdminOrSuperAdmin
from .models import (
    Department,
    Designation,
    Staff,
    StaffEmployment,
    TeacherAssignment,
    StaffQualification,
    StaffDocument
)
from .serializers import (
    DepartmentSerializer,
    DesignationSerializer,
    StaffSerializer,
    StaffProvisioningSerializer,
    StaffEmploymentSerializer,
    TeacherAssignmentSerializer,
    StaffQualificationSerializer,
    StaffDocumentSerializer
)
from .filters import (
    DepartmentFilter,
    DesignationFilter,
    StaffFilter,
    TeacherAssignmentFilter
)

class IsStaffAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_authenticated and (
            request.user.is_superuser or request.user.roles.filter(name__in=['ADMIN', 'SUPER_ADMIN']).exists()
        )


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.select_related('head').all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffAdminOrReadOnly]
    filterset_class = DepartmentFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'created_at']


class DesignationViewSet(viewsets.ModelViewSet):
    queryset = Designation.objects.all()
    serializer_class = DesignationSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffAdminOrReadOnly]
    filterset_class = DesignationFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'category']


class StaffViewSet(viewsets.ModelViewSet):
    queryset = Staff.objects.select_related('user').prefetch_related(
        'employment_records__department', 'employment_records__designation',
        'teaching_assignments__academic_session', 'teaching_assignments__class_obj',
        'teaching_assignments__subject', 'qualifications', 'documents'
    ).all()
    serializer_class = StaffSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = StaffFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['first_name', 'last_name', 'user__login_id', 'user__email', 'phone_number']
    ordering_fields = ['last_name', 'created_at']

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.is_superuser or user.roles.filter(name__in=['ADMIN', 'SUPER_ADMIN']).exists():
            return qs
        if user.roles.filter(name='STAFF').exists() and hasattr(user, 'staff_profile'):
            return qs.filter(pk=user.staff_profile.pk)
        return qs.none()

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsAdminOrSuperAdmin])
    def provision(self, request):
        serializer = StaffProvisioningSerializer(data=request.data)
        if serializer.is_valid():
            staff, temp_password = serializer.save(admin_user=request.user)
            staff_data = StaffSerializer(staff, context={'request': request}).data
            return Response({
                "success": True,
                "message": f"Staff provisioned successfully with staff ID {staff.user.login_id}.",
                "data": {
                    "staff": staff_data,
                    "temporary_password": temp_password
                }
            }, status=status.HTTP_201_CREATED)
        return Response({
            "success": False,
            "message": "Staff provisioning failed.",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsAdminOrSuperAdmin])
    def upload_document(self, request, pk=None):
        staff = self.get_object()
        serializer = StaffDocumentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(staff=staff, uploaded_by=request.user)
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


class TeacherAssignmentViewSet(viewsets.ModelViewSet):
    queryset = TeacherAssignment.objects.select_related(
        'staff', 'academic_session', 'class_obj', 'class_arm', 'subject'
    ).all()
    serializer_class = TeacherAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffAdminOrReadOnly]
    filterset_class = TeacherAssignmentFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['staff__first_name', 'staff__last_name', 'class_obj__name', 'subject__name']
    ordering_fields = ['academic_session', 'class_obj__display_order']

    def perform_create(self, serializer):
        # Resolve UUIDs to model instances before saving
        from apps.academics.models import AcademicSession, Class, ClassArm, Subject
        from .models import Staff

        data = serializer.validated_data
        staff_instance = Staff.objects.get(pk=data['staff'].pk) if hasattr(data['staff'], 'pk') else Staff.objects.get(pk=data['staff'])
        session_instance = AcademicSession.objects.get(pk=data['academic_session'])
        class_instance = Class.objects.get(pk=data['class_obj'])
        arm_instance = ClassArm.objects.filter(pk=data.get('class_arm')).first() if data.get('class_arm') else None
        subject_instance = Subject.objects.filter(pk=data.get('subject')).first() if data.get('subject') else None

        serializer.save(
            staff=staff_instance,
            academic_session=session_instance,
            class_obj=class_instance,
            class_arm=arm_instance,
            subject=subject_instance
        )