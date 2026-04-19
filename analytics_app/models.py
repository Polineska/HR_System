from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class HRDataset(models.Model):
    class Kind(models.TextChoices):
        LEAVE = "leave", "Leave dataset"
        BURNOUT = "burnout", "Burnout dataset"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to="datasets/%Y/%m/%d/")
    is_active = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "kind", "is_active", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} | {self.kind} | {self.name}"


class UserSessionUpload(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=64, db_index=True)
    original_name = models.CharField(max_length=255)
    file = models.FileField(upload_to="uploads/%Y/%m/%d/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "session_key", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} | {self.original_name} | {self.created_at:%Y-%m-%d %H:%M}"


class CsvReport(models.Model):
    class Kind(models.TextChoices):
        LEAVE = "leave", "Leave"
        BURNOUT = "burnout", "Burnout"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    dataset = models.ForeignKey(HRDataset, on_delete=models.SET_NULL, null=True, blank=True)
    session_key = models.CharField(max_length=64, db_index=True, null=True, blank=True)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    file = models.FileField(upload_to="reports/%Y/%m/%d/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} | {self.kind} | {self.created_at:%Y-%m-%d %H:%M}"
