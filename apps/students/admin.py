from django.contrib import admin
from .models import Student, StudentGuardian, StudentEnrollment, StudentDocument

class StudentGuardianInline(admin.TabularInline):
    model = StudentGuardian
    extra = 1
    autocomplete_fields = ('guardian',)

class StudentEnrollmentInline(admin.TabularInline):
    model = StudentEnrollment
    extra = 1

class StudentDocumentInline(admin.TabularInline):
    model = StudentDocument
    extra = 1

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    """
    Admin configuration for Student profiles, featuring search by admission number (user.login_id),
    status filtering, and integrated inlines for guardians, enrollments, and documents.
    """
    list_display = ('get_admission_number', 'first_name', 'last_name', 'gender', 'status', 'admission_date', 'created_at')
    list_filter = ('status', 'gender', 'admission_date')
    search_fields = ('first_name', 'last_name', 'user__login_id', 'user__email')
    ordering = ('last_name', 'first_name')
    inlines = [StudentGuardianInline, StudentEnrollmentInline, StudentDocumentInline]
    readonly_fields = ('id', 'created_at', 'updated_at')

    def get_admission_number(self, obj):
        return obj.user.login_id if obj.user else "-"
    get_admission_number.short_description = 'Admission No'
    get_admission_number.admin_order_field = 'user__login_id'


@admin.register(StudentGuardian)
class StudentGuardianAdmin(admin.ModelAdmin):
    list_display = ('student', 'guardian', 'relationship_type', 'is_primary', 'is_emergency_contact')
    list_filter = ('relationship_type', 'is_primary', 'is_emergency_contact')
    search_fields = ('student__first_name', 'student__last_name', 'student__user__login_id', 'guardian__email', 'guardian__first_name', 'guardian__last_name')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(StudentEnrollment)
class StudentEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'academic_session', 'class_obj', 'class_arm', 'status', 'enrollment_type')
    list_filter = ('academic_session', 'status', 'enrollment_type', 'class_obj')
    search_fields = ('student__first_name', 'student__last_name', 'student__user__login_id', 'class_obj__name')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(StudentDocument)
class StudentDocumentAdmin(admin.ModelAdmin):
    list_display = ('student', 'document_type', 'description', 'uploaded_by', 'created_at')
    list_filter = ('document_type',)
    search_fields = ('student__first_name', 'student__last_name', 'student__user__login_id', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')