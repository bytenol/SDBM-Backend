import django_filters
from .models import Student, StudentEnrollment

class StudentFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(lookup_expr='iexact')
    gender = django_filters.CharFilter(lookup_expr='iexact')
    state_of_origin = django_filters.CharFilter(lookup_expr='icontains')
    admission_year = django_filters.NumberFilter(field_name='admission_date', lookup_expr='year')
    class_id = django_filters.UUIDFilter(method='filter_by_class')
    session_id = django_filters.UUIDFilter(method='filter_by_session')

    class Meta:
        model = Student
        fields = ['status', 'gender', 'state_of_origin']

    def filter_by_class(self, queryset, name, value):
        return queryset.filter(enrollments__class_obj_id=value)

    def filter_by_session(self, queryset, name, value):
        return queryset.filter(enrollments__academic_session_id=value)