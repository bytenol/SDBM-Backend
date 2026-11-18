import django_filters
from django.db.models import Q
from .models import AuditLog


class AuditLogFilter(django_filters.FilterSet):
    actor = django_filters.UUIDFilter(field_name='actor__id')
    actor_identifier = django_filters.CharFilter(lookup_expr='icontains')
    action = django_filters.CharFilter(lookup_expr='iexact')
    category = django_filters.CharFilter(lookup_expr='iexact')
    model_name = django_filters.CharFilter(method='filter_by_model_name')
    object_id = django_filters.CharFilter(lookup_expr='exact')
    ip_address = django_filters.CharFilter(lookup_expr='icontains')
    start_date = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    end_date = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    search = django_filters.CharFilter(method='filter_search')

    class Meta:
        model = AuditLog
        fields = ['actor', 'actor_identifier', 'action', 'category', 'object_id', 'ip_address']

    def filter_by_model_name(self, queryset, name, value):
        return queryset.filter(content_type__model__iexact=value.lower())

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(description__icontains=value) |
            Q(object_repr__icontains=value) |
            Q(actor_identifier__icontains=value)
        )