from django.contrib import admin
from .models import (
    Department,
    Designation,
    Staff,
    StaffEmployment,
    TeacherAssignment,
    StaffQualification,
    StaffDocument
)

class StaffEmploymentInline(admin.TabularInline):
    model = StaffEmployment
    extra = 1
    fields = ('department', 'designation', 'employment_type', 'start_date', 'end_date', 'status')


class TeacherAssignmentInline(admin.TabularInline):
    model = TeacherAssignment
    extra = 1
    fields = ('academic_session', 'class_obj', 'class_arm', 'subject', 'assignment_type', 'is_class_teacher', 'is_active')


class StaffQualificationInline(admin.TabularInline):
    model = StaffQualification
    extra = 1
    fields = ('qualification_name', 'institution', 'qualification_level', 'completion_year')


class StaffDocumentInline(admin.TabularInline):
    model = StaffDocument
    extra = 1
    fields = ('document_type', 'file', 'description')


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'head', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'head__first_name', 'head__last_name')
    autocomplete_fields = ('head',)
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(Designation)
class DesignationAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'category', 'is_active', 'created_at')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'code')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('get_staff_id', 'first_name', 'last_name', 'gender', 'phone_number', 'created_at')
    list_filter = ('gender', 'employment_records__status', 'employment_records__department')
    search_fields = ('first_name', 'last_name', 'user__login_id', 'user__email', 'phone_number')
    ordering = ('last_name', 'first_name')
    inlines = [StaffEmploymentInline, TeacherAssignmentInline, StaffQualificationInline, StaffDocumentInline]
    readonly_fields = ('id', 'created_at', 'updated_at')

    def get_staff_id(self, obj):
        return obj.user.login_id if obj.user else "-"
    get_staff_id.short_description = 'Staff ID'
    get_staff_id.admin_order_field = 'user__login_id'


@admin.register(StaffEmployment)
class StaffEmploymentAdmin(admin.ModelAdmin):
    list_display = ('staff', 'department', 'designation', 'employment_type', 'status', 'start_date')
    list_filter = ('status', 'employment_type', 'department', 'designation')
    search_fields = ('staff__first_name', 'staff__last_name', 'staff__user__login_id', 'department__name', 'designation__name')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(TeacherAssignment)
class TeacherAssignmentAdmin(admin.ModelAdmin):
    list_display = ('staff', 'academic_session', 'class_obj', 'class_arm', 'subject', 'assignment_type', 'is_class_teacher', 'is_active')
    list_filter = ('academic_session', 'assignment_type', 'is_class_teacher', 'is_active', 'class_obj')
    search_fields = ('staff__first_name', 'staff__last_name', 'staff__user__login_id', 'class_obj__name', 'subject__name')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(StaffQualification)
class StaffQualificationAdmin(admin.ModelAdmin):
    list_display = ('staff', 'qualification_name', 'institution', 'completion_year')
    list_filter = ('completion_year', 'qualification_level')
    search_fields = ('staff__first_name', 'staff__last_name', 'qualification_name', 'institution')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(StaffDocument)
class StaffDocumentAdmin(admin.ModelAdmin):
    list_display = ('staff', 'document_type', 'description', 'uploaded_by', 'created_at')
    list_filter = ('document_type',)
    search_fields = ('staff__first_name', 'staff__last_name', 'staff__user__login_id', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')