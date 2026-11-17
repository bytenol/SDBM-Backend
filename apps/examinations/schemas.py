from rest_framework import serializers
from .serializers import StudentScoreSerializer


class BulkScoreEntryResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=True)
    message = serializers.CharField()
    data = StudentScoreSerializer(many=True)


class ScoreSubmitDataSerializer(serializers.Serializer):
    submitted_count = serializers.IntegerField()


class SubjectScoreSubmitResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=True)
    message = serializers.CharField()
    data = ScoreSubmitDataSerializer()


class ComputeResultDataSerializer(serializers.Serializer):
    computed_students_count = serializers.IntegerField()


class ClassResultComputeResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=True)
    message = serializers.CharField()
    data = ComputeResultDataSerializer()


class WorkflowTransitionDataSerializer(serializers.Serializer):
    updated_count = serializers.IntegerField()
    new_status = serializers.CharField()


class ClassResultWorkflowResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=True)
    message = serializers.CharField()
    data = WorkflowTransitionDataSerializer()


class ReportCardResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=True)
    data = serializers.DictField(help_text="Structured report card payload containing school_info, student_info, academic_context, performance_summary, subjects, and remarks_and_approval.")