"""Business logic for driver logs. Views call these; these call repositories. All
``@staticmethod``; mutations run inside ``transaction.atomic()``; domain rules raise
``apps.driver_logs.exceptions``.

An SOS log (``event_type == SOS``) is the alerts/notifications producer: after the row
commits it fires the real-time admin broadcast + one persistent EMERGENCY notification
per admin. Both are **best-effort** (wrapped, never raise) — the committed ``DriverLog``
is the audit record that matters, so the SOS endpoint still returns 201 even if fan-out
degrades. Keying the side-effect on ``event_type`` (not the endpoint) means
``/driver/sos/`` and a ``/driver/logs/`` post with ``event_type=sos`` produce the same
effect, with no duplication.
"""

import logging

from django.db import transaction

from apps.driver_logs import realtime as dl_realtime
from apps.driver_logs.enums import DriverLogEventType
from apps.driver_logs.exceptions import InvalidTripForLogError
from apps.driver_logs.models import DriverLog
from apps.driver_logs.repository import DriverLogRepository
from apps.notifications.enums import NotificationType
from apps.notifications.v1.service import NotificationService
from apps.trips.models import Trip
from apps.trips.repository import TripRepository

logger = logging.getLogger(__name__)


class DriverLogService:
    @staticmethod
    def create_log(driver, event_type, notes: str = "", trip=None) -> DriverLog:
        """Persist a driver log (atomic). A supplied ``trip`` (a ``Trip`` instance or its
        id) must belong to ``driver`` (else ``InvalidTripForLogError``). On an SOS log,
        fire the best-effort admin fan-out AFTER the commit so subscribers/recipients
        only learn of a persisted row.
        """
        if trip is not None:
            if not isinstance(trip, Trip):
                # ``trip`` arrived as an id (the serializer validates it's an int but
                # defers ownership here). Resolve it through the repository.
                trip = TripRepository.get_by_id(trip)
            # A missing trip is as invalid as an unowned one — don't leak existence.
            if trip is None or trip.driver_id != driver.id:
                raise InvalidTripForLogError()

        with transaction.atomic():
            log = DriverLogRepository.create(
                {
                    "driver": driver,
                    "trip": trip,
                    "event_type": event_type,
                    "notes": notes or "",
                }
            )

        if event_type == DriverLogEventType.SOS:
            DriverLogService._raise_sos_alert(log)
        return log

    @staticmethod
    def _raise_sos_alert(log: DriverLog) -> None:
        """Fan an SOS out to admins. Best-effort end-to-end: a broadcast or per-admin
        notify failure is swallowed + logged and NEVER breaks the committed SOS log.
        """
        payload = {
            "event": "SOS",
            "log_id": log.id,
            "driver_id": log.driver_id,
            "trip_id": log.trip_id,
            "notes": log.notes,
            "timestamp": log.timestamp.isoformat(),
        }
        # push_alert is itself best-effort, but guard the whole fan-out so a failure in
        # resolving recipients (admins()) can't break the SOS either. Called via the
        # module (dl_realtime.push_alert) so it's patchable at its definition site.
        try:
            dl_realtime.push_alert(payload)
            for admin in DriverLogRepository.admins():
                NotificationService.create(
                    admin,
                    NotificationType.EMERGENCY,
                    {
                        "driver_id": log.driver_id,
                        "trip_id": log.trip_id,
                        "log_id": log.id,
                        "notes": log.notes,
                    },
                )
        except Exception:  # noqa: BLE001 — SOS fan-out is best-effort; never break the log
            logger.warning("SOS fan-out failed for driver log %s", log.id, exc_info=True)
