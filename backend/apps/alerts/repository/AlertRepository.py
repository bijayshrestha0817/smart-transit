"""Data access for Alert. All Alert ORM lives here."""

from apps.alerts.enums import AlertStatus
from apps.alerts.models import Alert
from apps.common.repository import BaseRepository


class AlertRepository(BaseRepository):
    model = Alert

    @classmethod
    def feed(cls):
        # trip/route + driver are read on every alert row — select them up front. Ordering is
        # the model default (-created_at); the (status, -created_at) index serves filtered feeds.
        return Alert.objects.select_related("trip", "trip__route", "driver")

    @classmethod
    def open(cls):
        return cls.feed().filter(status=AlertStatus.OPEN)

    @classmethod
    def get_by_id(cls, alert_id):
        return cls.feed().filter(id=alert_id).first()

    @classmethod
    def create(cls, data: dict) -> Alert:
        return Alert.objects.create(**data)
