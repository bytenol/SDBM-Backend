import uuid
from django.db import models


class TimeStampedUUIDModel(models.Model):
    """
    An abstract base model class that provides self-updating
    uuid primary key, created_at, and updated_at fields.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID primary key"
    )

    created_at = models.DateTimeField(auto_now_add=True, help_text="Timestamp when the record was created")
    
    updated_at = models.DateTimeField(auto_now=True, help_text="Timestamp when the record was last updated")


    class Meta:
        abstract = True