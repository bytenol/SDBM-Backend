from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import (
    SchoolSettings,
    AcademicSession,
    AcademicTerm,
    Class,
    ClassArm,
    Subject,
    ClassSubject
)

class AcademicTermInline(admin.TabularInline):
    model = AcademicTerm
    extra = 1
    fields = ('name', 'start_date', 'end_date', 'is_current')

class ClassArmInline(admin.TabularInline):
    model = ClassArm
    extra = 1
    fields = ('name', 'code', 'capacity', 'is_active')

class ClassSubjectInline(admin.TabularInline):
    model = ClassSubject
    extra = 1
    fields = ('subject', 'is_compulsory', 'display_order', 'is_active')
    autocomplete_fields = ('subject',)


@admin.register(SchoolSettings)
class SchoolSettingsAdmin(admin.ModelAdmin):
    list_display = ('school_name', 'school_code', 'contact_email', 'current_session', 'current_term', 'updated_at')
    fieldsets = (
        ('Institutional Identity', {
            'fields': ('school_name', 'school_code', 'logo', 'description')
        }),
        ('Contact & Web', {
            'fields': ('address', 'contact_email', 'phone_number', 'website')
        }),
        ('Active Academic Context', {
            'fields': ('current_session', 'current_term')
        }),
    )
    readonly_fields = ('created_at', 'updated_at')

    def has_add_permission(self, request):
        # Enforce Singleton: prevent adding more than one settings record if one exists
        if SchoolSettings.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        # Prevent deleting institutional settings
        return False


@admin.register(AcademicSession)
class AcademicSessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_current', 'created_at')
    list_filter = ('is_current', 'start_date')
    search_fields = ('name',)
    ordering = ('-start_date',)
    inlines = [AcademicTermInline]
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(AcademicTerm)
class AcademicTermAdmin(admin.ModelAdmin):
    list_display = ('get_term_display', 'session', 'start_date', 'end_date', 'is_current')
    list_filter = ('is_current', 'name', 'session')
    search_fields = ('name', 'session__name')
    ordering = ('-session__start_date', 'name')
    readonly_fields = ('id', 'created_at', 'updated_at')

    def get_term_display(self, obj):
        return obj.get_name_display()
    get_term_display.short_description = 'Term'


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'education_level', 'display_order', 'is_active')
    list_filter = ('education_level', 'is_active')
    search_fields = ('name', 'code')
    ordering = ('display_order', 'name')
    inlines = [ClassArmInline, ClassSubjectInline]
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(ClassArm)
class ClassArmAdmin(admin.ModelAdmin):
    list_display = ('name', 'class_obj', 'code', 'capacity', 'is_active')
    list_filter = ('is_active', 'class_obj__education_level', 'class_obj')
    search_fields = ('name', 'code', 'class_obj__name')
    ordering = ('class_obj__display_order', 'name')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'category', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'code')
    ordering = ('name',)
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(ClassSubject)
class ClassSubjectAdmin(admin.ModelAdmin):
    list_display = ('class_obj', 'subject', 'is_compulsory', 'display_order', 'is_active')
    list_filter = ('is_compulsory', 'is_active', 'class_obj', 'subject__category')
    search_fields = ('class_obj__name', 'subject__name', 'subject__code')
    ordering = ('class_obj__display_order', 'display_order')
    readonly_fields = ('id', 'created_at', 'updated_at')