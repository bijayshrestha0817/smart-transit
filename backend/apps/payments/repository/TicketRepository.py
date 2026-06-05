"""Data access for Ticket. All Ticket ORM lives here."""

from apps.common.repository import BaseRepository
from apps.payments.models import Ticket


class TicketRepository(BaseRepository):
    model = Ticket

    @classmethod
    def active(cls):
        # passenger/trip/route + the 1:1 payment are read on every ticket response.
        return Ticket.objects.select_related("passenger", "trip", "trip__route", "payment")

    @classmethod
    def get_by_id(cls, ticket_id):
        return cls.active().filter(id=ticket_id).first()

    @classmethod
    def for_passenger(cls, passenger):
        return cls.active().filter(passenger=passenger)

    @classmethod
    def create(cls, data: dict) -> Ticket:
        return Ticket.objects.create(**data)
