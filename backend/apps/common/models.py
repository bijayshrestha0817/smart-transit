"""Shared abstract base model implementing timestamps + soft delete.

Every domain table (routes, buses, trips, tickets, …) inherits this. The custom
``User`` model defines the same three fields directly because it needs its own
manager (``UserManager``) for createsuperuser to work.
"""

from django.db import models


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        """Soft-delete the whole queryset (mark, don't drop)."""
        return super().update(is_deleted=True)

    def hard_delete(self):
        """Permanently remove rows — admin/maintenance use only."""
        return super().delete()


class SoftDeleteManager(models.Manager):
    """Default manager: hides soft-deleted rows."""

    def get_queryset(self) -> SoftDeleteQuerySet:
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)


class TimeStampedSoftDeleteModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    objects = SoftDeleteManager()  # excludes soft-deleted rows
    all_objects = models.Manager()  # noqa: DJ012 — second (escape-hatch) manager on abstract base

    class Meta:
        abstract = True
        get_latest_by = "created_at"
        ordering = ("-created_at",)

    def delete(self, using=None, keep_parents=False):
        """Soft delete: flag the row instead of removing it."""
        self.is_deleted = True
        self.save(using=using, update_fields=["is_deleted", "updated_at"])

    def hard_delete(self, using=None, keep_parents=False):
        super().delete(using=using, keep_parents=keep_parents)
