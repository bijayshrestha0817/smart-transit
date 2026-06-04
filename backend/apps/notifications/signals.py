"""Decoupled trip-event producer: a ``post_save`` receiver on ``trips.Trip``.

When a trip transitions to COMPLETED (``end_trip`` saves
``update_fields=["status", "end_time", "updated_at"]``), produce a TRIP_COMPLETED
notification for the trip's driver. This lives in ``apps.notifications`` and touches
NO trips code — the coupling is one-way (notifications → trips) via a signal.

Idempotent: skipped if a TRIP_COMPLETED notification for this (driver, trip_id)
already exists, so re-saving a completed trip never duplicates.

**The whole body is wrapped in try/except → log + swallow** (like
``realtime/broadcast.py``): a notification failure must NEVER break ``end_trip``, the
committed write that actually matters. The handler runs inside end_trip's transaction,
so the notification row commits atomically with the trip; only delivery is deferred to
``on_commit`` inside the service.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notifications.enums import NotificationType
from apps.notifications.repository import NotificationRepository
from apps.notifications.v1.service import NotificationService
from apps.trips.enums import TripStatus
from apps.trips.models import Trip

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Trip, dispatch_uid="notifications_trip_completed")
def notify_driver_on_trip_completed(sender, instance, created, update_fields=None, **kwargs):
    """Produce a TRIP_COMPLETED notification for the driver when a trip completes."""
    try:
        # Only fire on the status-bearing save that transitions to COMPLETED. end_trip
        # passes update_fields=["status", ...]; a create or a non-status save is ignored.
        if instance.status != TripStatus.COMPLETED:
            return
        if "status" not in (update_fields or []):
            return
        if NotificationRepository.exists_for_trip(
            instance.driver, NotificationType.TRIP_COMPLETED, instance.id
        ):
            return  # idempotent — already produced for this trip+driver
        NotificationService.create(
            instance.driver,
            NotificationType.TRIP_COMPLETED,
            {"trip_id": instance.id, "route_name": instance.route.name},
        )
    except Exception:  # noqa: BLE001 — a notification failure must never break end_trip
        logger.warning(
            "notify_driver_on_trip_completed failed for trip %s", instance.pk, exc_info=True
        )
