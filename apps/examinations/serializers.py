from rest_framework import serializers
from .models import (
    Examination,
    AssessmentComponent,
    GradingScale,
    StudentScore,
    StudentResult,
    StudentTermSummary,
    ResultWorkflowAudit,
    ResultWorkflowStatus,
)


class ExaminationSerializer(serializers.ModelSerializer):
    session_name = serializers.ReadOnlyField(source='academic_session.name')
    term_name = serializers.ReadOnlyField(source='academic_term.get_name_display')

    class Meta:
        model = Examination
        fields = [
            'id', 'name', 'examination_type', 'academic_session', 'session_name',
            'academic_term', 'term_name', 'applicable_classes', 'start_date',
            'end_date', 'status', 'is_active', 'instructions', 'remarks',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        instance = Examination(**attrs)
        if self.instance:
            for attr, value in attrs.items():
                setattr(self.instance, attr, value)
            self.instance.clean()
        else:
            instance.clean()
        return attrs


class AssessmentComponentSerializer(serializers.ModelSerializer):
    session_name = serializers.ReadOnlyField(source='academic_session.name')
    term_name = serializers.ReadOnlyField(source='academic_term.get_name_display')
    class_name = serializers.ReadOnlyField(source='class_obj.name')

    class Meta:
        model = AssessmentComponent
        fields = [
            'id', 'academic_session', 'session_name', 'academic_term', 'term_name',
            'class_obj', 'class_name', 'category', 'name', 'code',
            'maximum_score', 'weight_percentage', 'display_order', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        if self.instance:
            for attr, value in attrs.items():
                setattr(self.instance, attr, value)
            self.instance.clean()
        else:
            AssessmentComponent(**attrs).clean()
        return attrs


class GradingScaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradingScale
        fields = [
            'id', 'academic_session', 'education_level', 'grade_letter',
            'min_score', 'max_score', 'grade_point', 'remark', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        if self.instance:
            for attr, value in attrs.items():
                setattr(self.instance, attr, value)
            self.instance.clean()
        else:
            GradingScale(**attrs).clean()
        return attrs


class StudentScoreSerializer(serializers.ModelSerializer):
    student_id = serializers.ReadOnlyField(source='student_enrollment.student.id')
    admission_number = serializers.ReadOnlyField(source='student_enrollment.student.user.login_id')
    student_name = serializers.SerializerMethodField()
    subject_name = serializers.ReadOnlyField(source='subject.name')
    subject_code = serializers.ReadOnlyField(source='subject.code')
    component_code = serializers.ReadOnlyField(source='assessment_component.code')
    weighted_score = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)

    class Meta:
        model = StudentScore
        fields = [
            'id', 'student_enrollment', 'student_id', 'admission_number', 'student_name',
            'academic_term', 'subject', 'subject_name', 'subject_code',
            'assessment_component', 'component_code', 'examination',
            'score', 'is_absent', 'is_exempted', 'max_score_snapshot',
            'weight_snapshot', 'weighted_score', 'status', 'entered_by',
            'last_modified_by', 'submitted_at', 'remarks', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'max_score_snapshot', 'weight_snapshot', 'weighted_score',
            'status', 'entered_by', 'last_modified_by', 'submitted_at',
            'created_at', 'updated_at',
        ]

    def get_student_name(self, obj) -> str:
        s = obj.student_enrollment.student
        return f"{s.last_name}, {s.first_name} {s.middle_name or ''}".strip()


class SingleScoreEntryInputSerializer(serializers.Serializer):
    student_enrollment = serializers.UUIDField(required=True)
    score = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    is_absent = serializers.BooleanField(default=False)
    is_exempted = serializers.BooleanField(default=False)
    remarks = serializers.CharField(max_length=255, required=False, allow_blank=True)


class BulkScoreEntrySerializer(serializers.Serializer):
    academic_term = serializers.UUIDField(required=True)
    class_obj = serializers.UUIDField(required=True)
    class_arm = serializers.UUIDField(required=False, allow_null=True)
    subject = serializers.UUIDField(required=True)
    assessment_component = serializers.UUIDField(required=True)
    scores = SingleScoreEntryInputSerializer(many=True, min_length=1)


class SubjectScoreSubmitSerializer(serializers.Serializer):
    academic_term = serializers.UUIDField(required=True)
    class_obj = serializers.UUIDField(required=True)
    class_arm = serializers.UUIDField(required=False, allow_null=True)
    subject = serializers.UUIDField(required=True)


class ClassResultComputeSerializer(serializers.Serializer):
    academic_term = serializers.UUIDField(required=True)
    class_obj = serializers.UUIDField(required=True)
    class_arm = serializers.UUIDField(required=False, allow_null=True)


class ClassResultWorkflowSerializer(serializers.Serializer):
    academic_term = serializers.UUIDField(required=True)
    class_obj = serializers.UUIDField(required=True)
    class_arm = serializers.UUIDField(required=False, allow_null=True)
    target_status = serializers.ChoiceField(choices=ResultWorkflowStatus.choices, required=True)
    reason = serializers.CharField(required=False, allow_blank=True)


class StudentResultSerializer(serializers.ModelSerializer):
    student_id = serializers.ReadOnlyField(source='student_enrollment.student.id')
    admission_number = serializers.ReadOnlyField(source='student_enrollment.student.user.login_id')
    student_name = serializers.SerializerMethodField()
    subject_name = serializers.ReadOnlyField(source='subject.name')
    subject_code = serializers.ReadOnlyField(source='subject.code')

    class Meta:
        model = StudentResult
        fields = [
            'id', 'student_enrollment', 'student_id', 'admission_number', 'student_name',
            'academic_term', 'subject', 'subject_name', 'subject_code',
            'ca_total', 'exam_score', 'total_score', 'grade', 'grade_point',
            'remark', 'subject_position', 'class_highest', 'class_lowest',
            'class_average', 'is_incomplete', 'status', 'computed_at',
        ]
        read_only_fields = fields

    def get_student_name(self, obj) -> str:
        s = obj.student_enrollment.student
        return f"{s.last_name}, {s.first_name} {s.middle_name or ''}".strip()


class StudentTermSummarySerializer(serializers.ModelSerializer):
    student_id = serializers.ReadOnlyField(source='student_enrollment.student.id')
    admission_number = serializers.ReadOnlyField(source='student_enrollment.student.user.login_id')
    student_name = serializers.SerializerMethodField()
    session_name = serializers.ReadOnlyField(source='student_enrollment.academic_session.name')
    term_name = serializers.ReadOnlyField(source='academic_term.get_name_display')
    class_name = serializers.ReadOnlyField(source='student_enrollment.class_obj.name')
    class_arm_name = serializers.ReadOnlyField(source='student_enrollment.class_arm.name')
    subject_results = serializers.SerializerMethodField()

    class Meta:
        model = StudentTermSummary
        fields = [
            'id', 'student_enrollment', 'student_id', 'admission_number', 'student_name',
            'session_name', 'academic_term', 'term_name', 'class_name', 'class_arm_name',
            'subjects_offered', 'subjects_passed', 'total_score', 'average_score',
            'gpa', 'class_position', 'arm_position', 'total_students_in_class',
            'teacher_remarks', 'principal_remarks', 'status', 'approved_by',
            'approved_at', 'published_by', 'published_at', 'subject_results',
        ]
        read_only_fields = [
            'id', 'student_enrollment', 'academic_term', 'subjects_offered',
            'subjects_passed', 'total_score', 'average_score', 'gpa',
            'class_position', 'arm_position', 'total_students_in_class',
            'status', 'approved_by', 'approved_at', 'published_by', 'published_at',
        ]

    def get_student_name(self, obj) -> str:
        s = obj.student_enrollment.student
        return f"{s.last_name}, {s.first_name} {s.middle_name or ''}".strip()

    def get_subject_results(self, obj):
        results = StudentResult.objects.filter(
            student_enrollment=obj.student_enrollment,
            academic_term=obj.academic_term
        ).select_related('subject').order_by('subject__name')
        return StudentResultSerializer(results, many=True).data


class ResultWorkflowAuditSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.ReadOnlyField(source='performed_by.get_full_name')
    class_name = serializers.ReadOnlyField(source='class_obj.name')
    subject_name = serializers.ReadOnlyField(source='subject.name')

    class Meta:
        model = ResultWorkflowAudit
        fields = [
            'id', 'academic_session', 'academic_term', 'class_obj', 'class_name',
            'class_arm', 'subject', 'subject_name', 'previous_status', 'new_status',
            'performed_by', 'performed_by_name', 'reason', 'created_at',
        ]
        read_only_fields = fields