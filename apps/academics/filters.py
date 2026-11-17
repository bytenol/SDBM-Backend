import django_filters
from .models import (
    AcademicSession,
    AcademicTerm,
    Class,
    ClassArm,
    Subject,
    ClassSubject
)

class AcademicSessionFilter(django_filters.FilterSet):
    is_current = django_filters.BooleanFilter()

    class Meta:
        model = AcademicSession
        fields = ['is_current']


class AcademicTermFilter(django_filters.FilterSet):
    session = django_filters.UUIDFilter()
    is_current = django_filters.BooleanFilter()
    name = django_filters.CharFilter(lookup_expr='iexact')

    class Meta:
        model = AcademicTerm
        fields = ['session', 'is_current', 'name']


class ClassFilter(django_filters.FilterSet):
    education_level = django_filters.CharFilter(lookup_expr='iexact')
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = Class
        fields = ['education_level', 'is_active']


class ClassArmFilter(django_filters.FilterSet):
    class_obj = django_filters.UUIDFilter()
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = ClassArm
        fields = ['class_obj', 'is_active']


class SubjectFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(lookup_expr='iexact')
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = Subject
        fields = ['category', 'is_active']


class ClassSubjectFilter(django_filters.FilterSet):
    class_obj = django_filters.UUIDFilter()
    subject = django_filters.UUIDFilter()
    is_compulsory = django_filters.BooleanFilter()
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = ClassSubject
        fields = ['class_obj', 'subject', 'is_compulsory', 'is_active']