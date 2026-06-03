"""BaseRepository — shared, soft-delete-aware data-access helpers.

ALL ORM access lives in repositories (one class per model, static/class methods).
Services call repositories; views never touch the ORM. Subclasses set ``model`` and
add query methods that shape data with ``select_related`` / ``prefetch_related`` to
match what the serializer will access.
"""

from django.db import models


class BaseRepository:
    model: type[models.Model]

    @classmethod
    def active(cls) -> models.QuerySet:
        """Base queryset. For models on ``SoftDeleteManager`` this already excludes
        soft-deleted rows; override per repository to add default ``select_related``."""
        return cls.model.objects.all()

    @classmethod
    def get_or_none(cls, **filters):
        """Fetch a single active row or ``None`` (services decide whether absence is an error)."""
        return cls.active().filter(**filters).first()

    @classmethod
    def apply_update(cls, instance, data: dict, *, extra_fields=("updated_at",)):
        """Set ``data`` onto ``instance`` and persist via ``update_fields`` (PATCH idiom)."""
        fields = []
        for field, value in data.items():
            setattr(instance, field, value)
            fields.append(field)
        instance.save(update_fields=[*fields, *extra_fields])
        return instance
