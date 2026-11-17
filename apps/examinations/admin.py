from django.contrib import admin
from .models import (
    Examination,
    AssessmentComponent,
    GradingScale,
    StudentScore,
    StudentResult,
    StudentTermSummary,
    ResultWorkflowAudit,
)


@admin.register(Examination)
class ExaminationAdmin(admin.ModelAdmin):
    list_display = ('name', 'examination_type', 'academic_session', 'academic_term', 'start_date', 'end_date', 'status', 'is_active')
    list_filter = ('examination_type', 'status', 'is_active', 'academic_session')
    search_fields = ('name', 'academic_session__name')
    filter_horizontal = ('applicable_classes',)
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(AssessmentComponent)
class AssessmentComponentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'category', 'maximum_score', 'weight_percentage', 'class_obj', 'academic_session', 'academic_term', 'is_active')
    list_filter = ('category', 'is_active', 'academic_session', 'academic_term', 'class_obj')
    search_fields = ('name', 'code')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(GradingScale)
class GradingScaleAdmin(admin.ModelAdmin):
    list_display = ('grade_letter', 'min_score', 'max_score', 'grade_point', 'remark', 'education_level', 'academic_session', 'is_active')
    list_filter = ('is_active', 'education_level', 'academic_session')
    search_fields = ('grade_letter', 'remark')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(StudentScore)
class StudentScoreAdmin(admin.ModelAdmin):
    list_display = ('student_enrollment', 'academic_term', 'subject', 'assessment_component', 'score', 'max_score_snapshot', 'status', 'entered_by')
    list_filter = ('status', 'is_absent', 'is_exempted', 'academic_term', 'subject')
    search_fields = (
        'student_enrollment__student__first_name',
        'student_enrollment__student__last_name',
        'student_enrollment__student__user__login_id',
        'subject__name',
    )
    readonly_fields = ('id', 'max_score_snapshot', 'weight_snapshot', 'submitted_at', 'created_at', 'updated_at')


@admin.register(StudentResult)
class StudentResultAdmin(admin.ModelAdmin):
    list_display = ('student_enrollment', 'academic_term', 'subject', 'ca_total', 'exam_score', 'total_score', 'grade', 'subject_position', 'status')
    list_filter = ('status', 'grade', 'is_incomplete', 'academic_term', 'subject')
    search_fields = (
        'student_enrollment__student__first_name',
        'student_enrollment__student__last_name',
        'student_enrollment__student__user__login_id',
        'subject__name',
    )
    readonly_fields = ('id', 'computed_at', 'created_at', 'updated_at')


@admin.register(StudentTermSummary)
class StudentTermSummaryAdmin(admin.ModelAdmin):
    list_display = ('student_enrollment', 'academic_term', 'subjects_offered', 'total_score', 'average_score', 'class_position', 'status')
    list_filter = ('status', 'academic_term', 'student_enrollment__class_obj')
    search_fields = (
        'student_enrollment__student__first_name',
        'student_enrollment__student__last_name',
        'student_enrollment__student__user__login_id',
    )
    readonly_fields = ('id', 'approved_at', 'published_at', 'created_at', 'updated_at')


@admin.register(ResultWorkflowAudit)
class ResultWorkflowAuditAdmin(admin.ModelAdmin):
    list_display = ('academic_session', 'academic_term', 'class_obj', 'subject', 'previous_status', 'new_status', 'performed_by', 'created_at')
    list_filter = ('previous_status', 'new_status', 'academic_session', 'academic_term')
    readonly_fields = ('id', 'created_at', 'updated_at')