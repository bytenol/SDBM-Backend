import django_filters
from .models import Staff, Department, Designation, StaffEmployment, TeacherAssignment


class DepartmentFilter(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter()
    name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Department
        fields = ['is_active', 'name']


class DesignationFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(lookup_expr='iexact')
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = Designation
        fields = ['category', 'is_active']


class StaffFilter(django_filters.FilterSet):
    gender = django_filters.CharFilter(lookup_expr='iexact')
    state_of_origin = django_filters.CharFilter(lookup_expr='icontains')
    department = django_filters.UUIDFilter(field_name='employment_records__department')
    designation = django_filters.UUIDFilter(field_name='employment_records__designation')
    status = django_filters.CharFilter(field_name='employment_records__status', lookup_expr='iexact')

    class Meta:
        model = Staff
        fields = ['gender', 'state_of_origin', 'department', 'designation', 'status']


class TeacherAssignmentFilter(django_filters.FilterSet):
    staff = django_filters.UUIDFilter()
    academic_session = django_filters.UUIDFilter()
    class_obj = django_filters.UUIDFilter()
    subject = django_filters.UUIDFilter()
    assignment_type = django_filters.CharFilter(lookup_expr='iexact')
    is_class_teacher = django_filters.BooleanFilter()
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = TeacherAssignment
        fields = ['staff', 'academic_session', 'class_obj', 'subject', 'assignment_type', 'is_class_teacher', 'is_active']