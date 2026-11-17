from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.accounts.permissions import IsAdminOrSuperAdmin
from .models import (
    SchoolSettings,
    AcademicSession,
    AcademicTerm,
    Class,
    ClassArm,
    Subject,
    ClassSubject
)
from .serializers import (
    SchoolSettingsSerializer,
    AcademicSessionSerializer,
    AcademicTermSerializer,
    ClassSerializer,
    ClassArmSerializer,
    SubjectSerializer,
    ClassSubjectSerializer
)
from .filters import (
    AcademicSessionFilter,
    AcademicTermFilter,
    ClassFilter,
    ClassArmFilter,
    SubjectFilter,
    ClassSubjectFilter
)

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Allows read-only access for authenticated users, 
    but restricts create/update/delete to admins/super admins.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_authenticated and (
            request.user.is_superuser or request.user.roles.filter(name__in=['ADMIN', 'SUPER_ADMIN']).exists()
        )


class SchoolSettingsView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request):
        settings_obj = SchoolSettings.load()
        serializer = SchoolSettingsSerializer(settings_obj)
        return Response({"success": True, "message": "School settings retrieved.", "data": serializer.data})

    def put(self, request):
        settings_obj = SchoolSettings.load()
        serializer = SchoolSettingsSerializer(settings_obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"success": True, "message": "School settings updated successfully.", "data": serializer.data})
        return Response({"success": False, "message": "Validation failed.", "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class AcademicSessionViewSet(viewsets.ModelViewSet):
    queryset = AcademicSession.objects.all()
    serializer_class = AcademicSessionSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_class = AcademicSessionFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['start_date', 'name']


class AcademicTermViewSet(viewsets.ModelViewSet):
    queryset = AcademicTerm.objects.select_related('session').all()
    serializer_class = AcademicTermSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_class = AcademicTermFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'session__name']
    ordering_fields = ['start_date', 'name']


class ClassViewSet(viewsets.ModelViewSet):
    queryset = Class.objects.prefetch_related('arms', 'class_subjects').all()
    serializer_class = ClassSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_class = ClassFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'code']
    ordering_fields = ['display_order', 'name']


class ClassArmViewSet(viewsets.ModelViewSet):
    queryset = ClassArm.objects.select_related('class_obj').all()
    serializer_class = ClassArmSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_class = ClassArmFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'code', 'class_obj__name']
    ordering_fields = ['name', 'class_obj__display_order']


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_class = SubjectFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'code']


class ClassSubjectViewSet(viewsets.ModelViewSet):
    queryset = ClassSubject.objects.select_related('class_obj', 'subject').all()
    serializer_class = ClassSubjectSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_class = ClassSubjectFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['class_obj__name', 'subject__name', 'subject__code']
    ordering_fields = ['class_obj__display_order', 'display_order']