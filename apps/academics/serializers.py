# apps/academics/serializers.py
from rest_framework import serializers
from .models import (
    SchoolSettings,
    AcademicSession,
    AcademicTerm,
    Class,
    ClassArm,
    Subject,
    ClassSubject
)

class AcademicTermSerializer(serializers.ModelSerializer):
    session_name = serializers.ReadOnlyField(source='session.name')
    term_display = serializers.CharField(source='get_name_display', read_only=True)

    class Meta:
        model = AcademicTerm
        fields = ['id', 'session', 'session_name', 'name', 'term_display', 'start_date', 'end_date', 'is_current', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        session = attrs.get('session', self.instance.session if self.instance else None)
        start_date = attrs.get('start_date', self.instance.start_date if self.instance else None)
        end_date = attrs.get('end_date', self.instance.end_date if self.instance else None)

        if start_date and end_date and start_date >= end_date:
            raise serializers.ValidationError({"end_date": "Term start date must be earlier than the end date."})

        if session and start_date and end_date:
            if start_date < session.start_date or end_date > session.end_date:
                raise serializers.ValidationError({"start_date": "Term dates must fall strictly within the parent session's dates."})

        return attrs


class AcademicSessionSerializer(serializers.ModelSerializer):
    terms = AcademicTermSerializer(many=True, read_only=True)

    class Meta:
        model = AcademicSession
        fields = ['id', 'name', 'start_date', 'end_date', 'is_current', 'terms', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        start_date = attrs.get('start_date', self.instance.start_date if self.instance else None)
        end_date = attrs.get('end_date', self.instance.end_date if self.instance else None)

        if start_date and end_date and start_date >= end_date:
            raise serializers.ValidationError({"end_date": "Session start date must be earlier than the end date."})
        return attrs


class SchoolSettingsSerializer(serializers.ModelSerializer):
    current_session_details = AcademicSessionSerializer(source='current_session', read_only=True)
    current_term_details = AcademicTermSerializer(source='current_term', read_only=True)

    class Meta:
        model = SchoolSettings
        fields = [
            'id', 'school_name', 'school_code', 'logo', 'address',
            'contact_email', 'phone_number', 'website', 'description',
            'current_session', 'current_session_details',
            'current_term', 'current_term_details',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ClassArmSerializer(serializers.ModelSerializer):
    class_name = serializers.ReadOnlyField(source='class_obj.name')

    class Meta:
        model = ClassArm
        fields = ['id', 'class_obj', 'class_name', 'name', 'code', 'capacity', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ClassSubjectSerializer(serializers.ModelSerializer):
    subject_name = serializers.ReadOnlyField(source='subject.name')
    subject_code = serializers.ReadOnlyField(source='subject.code')
    subject_category = serializers.ReadOnlyField(source='subject.category')

    class Meta:
        model = ClassSubject
        fields = ['id', 'class_obj', 'subject', 'subject_name', 'subject_code', 'subject_category', 'is_compulsory', 'display_order', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ClassSerializer(serializers.ModelSerializer):
    arms = ClassArmSerializer(many=True, read_only=True)
    class_subjects = ClassSubjectSerializer(many=True, read_only=True)
    education_level_display = serializers.CharField(source='get_education_level_display', read_only=True)

    class Meta:
        model = Class
        fields = ['id', 'name', 'code', 'education_level', 'education_level_display', 'description', 'display_order', 'is_active', 'arms', 'class_subjects', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class SubjectSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = Subject
        fields = ['id', 'name', 'code', 'description', 'category', 'category_display', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']