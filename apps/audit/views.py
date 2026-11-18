# apps/audit/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count

from apps.accounts.permissions import IsAdminOrSuperAdmin
from .models import AuditLog
from .serializers import AuditLogSerializer
from .filters import AuditLogFilter


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only administrative API for inspecting platform audit logs.
    Restricted strictly to SUPER_ADMIN and ADMIN roles.
    """
    queryset = AuditLog.objects.select_related('actor', 'content_type').all()
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrSuperAdmin]
    filterset_class = AuditLogFilter
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    @action(detail=False, methods=['get'], url_path='object-history')
    def object_history(self, request):
        """
        Returns chronological audit history for a specific model record:
        GET /api/v1/audit/logs/object-history/?model=student&object_id=<uuid>
        """
        model_name = request.query_params.get('model')
        object_id = request.query_params.get('object_id')

        if not model_name or not object_id:
            return Response(
                {"success": False, "error": "Both 'model' and 'object_id' query parameters are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            ct = ContentType.objects.get(model__iexact=model_name.lower())
        except ContentType.DoesNotExist:
            return Response(
                {"success": False, "error": f"Model '{model_name}' not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        logs = self.get_queryset().filter(content_type=ct, object_id=str(object_id))
        page = self.paginate_queryset(logs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(logs, many=True)
        return Response({"success": True, "data": serializer.data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """
        Returns aggregate security and activity statistics.
        GET /api/v1/audit/logs/summary/
        """
        qs = self.get_queryset()
        total_logs = qs.count()
        by_category = list(qs.values('category').annotate(count=Count('id')).order_by('-count'))
        by_action = list(qs.values('action').annotate(count=Count('id')).order_by('-count'))
        recent_failures = qs.filter(action='LOGIN_FAILED').count()

        return Response({
            "success": True,
            "data": {
                "total_logs_count": total_logs,
                "login_failed_count": recent_failures,
                "breakdown_by_category": by_category,
                "breakdown_by_action": by_action,
            }
        }, status=status.HTTP_200_OK)