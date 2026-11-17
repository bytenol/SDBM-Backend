import django_filters
from .models import (
    Examination,
    AssessmentComponent,
    GradingScale,
    StudentScore,
    StudentResult,
    StudentTermSummary,
)


class ExaminationFilter(django_filters.FilterSet):
    academic_session = django_filters.UUIDFilter()
    academic_term = django_filters.UUIDFilter()
    examination_type = django_filters.CharFilter(lookup_expr='iexact')
    status = django_filters.CharFilter(lookup_expr='iexact')
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = Examination
        fields = ['academic_session', 'academic_term', 'examination_type', 'status', 'is_active']


class AssessmentComponentFilter(django_filters.FilterSet):
    academic_session = django_filters.UUIDFilter()
    academic_term = django_filters.UUIDFilter()
    class_obj = django_filters.UUIDFilter()
    category = django_filters.CharFilter(lookup_expr='iexact')
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = AssessmentComponent
        fields = ['academic_session', 'academic_term', 'class_obj', 'category', 'is_active']


class GradingScaleFilter(django_filters.FilterSet):
    academic_session = django_filters.UUIDFilter()
    education_level = django_filters.CharFilter(lookup_expr='iexact')
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = GradingScale
        fields = ['academic_session', 'education_level', 'is_active']


class StudentScoreFilter(django_filters.FilterSet):
    student_enrollment = django_filters.UUIDFilter()
    student = django_filters.UUIDFilter(field_name='student_enrollment__student_id')
    academic_session = django_filters.UUIDFilter(field_name='student_enrollment__academic_session_id')
    academic_term = django_filters.UUIDFilter()
    class_obj = django_filters.UUIDFilter(field_name='student_enrollment__class_obj_id')
    class_arm = django_filters.UUIDFilter(field_name='student_enrollment__class_arm_id')
    subject = django_filters.UUIDFilter()
    assessment_component = django_filters.UUIDFilter()
    status = django_filters.CharFilter(lookup_expr='iexact')

    class Meta:
        model = StudentScore
        fields = [
            'student_enrollment', 'student', 'academic_session',
            'academic_term', 'class_obj', 'class_arm',
            'subject', 'assessment_component', 'status',
        ]


class StudentResultFilter(django_filters.FilterSet):
    student_enrollment = django_filters.UUIDFilter()
    student = django_filters.UUIDFilter(field_name='student_enrollment__student_id')
    academic_session = django_filters.UUIDFilter(field_name='student_enrollment__academic_session_id')
    academic_term = django_filters.UUIDFilter()
    class_obj = django_filters.UUIDFilter(field_name='student_enrollment__class_obj_id')
    class_arm = django_filters.UUIDFilter(field_name='student_enrollment__class_arm_id')
    subject = django_filters.UUIDFilter()
    grade = django_filters.CharFilter(lookup_expr='iexact')
    status = django_filters.CharFilter(lookup_expr='iexact')

    class Meta:
        model = StudentResult
        fields = [
            'student_enrollment', 'student', 'academic_session',
            'academic_term', 'class_obj', 'class_arm',
            'subject', 'grade', 'status',
        ]


class StudentTermSummaryFilter(django_filters.FilterSet):
    student_enrollment = django_filters.UUIDFilter()
    student = django_filters.UUIDFilter(field_name='student_enrollment__student_id')
    academic_session = django_filters.UUIDFilter(field_name='student_enrollment__academic_session_id')
    academic_term = django_filters.UUIDFilter()
    class_obj = django_filters.UUIDFilter(field_name='student_enrollment__class_obj_id')
    class_arm = django_filters.UUIDFilter(field_name='student_enrollment__class_arm_id')
    status = django_filters.CharFilter(lookup_expr='iexact')

    class Meta:
        model = StudentTermSummary
        fields = [
            'student_enrollment', 'student', 'academic_session',
            'academic_term', 'class_obj', 'class_arm', 'status',
        ]