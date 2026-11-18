from rest_framework import serializers
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    model_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            'id', 'actor', 'actor_identifier', 'actor_name',
            'action', 'category', 'content_type', 'model_name',
            'object_id', 'object_repr', 'description',
            'previous_values', 'new_values', 'metadata',
            'ip_address', 'user_agent', 'created_at',
        ]
        read_only_fields = fields

    def get_actor_name(self, obj) -> str:
        if obj.actor:
            return f"{obj.actor.first_name} {obj.actor.last_name}".strip() or obj.actor_identifier
        return obj.actor_identifier or "SYSTEM"

    def get_model_name(self, obj):
        if obj.content_type:
            return obj.content_type.model
        return None