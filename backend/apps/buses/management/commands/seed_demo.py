"""Idempotent demo seed: users across every role, plus Kathmandu-area routes,
ordered stops, and a small fleet wired to the demo drivers.

Safe to run repeatedly — every object is created via ``get_or_create`` keyed on a
natural identifier, and each demo account's password is (re)set to the known demo
value, so a second run converges to the same state. Run with::

    # local
    DJANGO_SETTINGS_MODULE=config.settings.dev python manage.py seed_demo

    # docker compose (stack already running)
    docker compose exec web python manage.py seed_demo

    # docker compose (stack not running — starts deps, then exits)
    docker compose run --rm web python manage.py seed_demo

Why passwords are set explicitly (not via the ``get_or_create`` defaults): a user
created through ``get_or_create`` is built with ``Model.create`` (not
``create_user``), so its ``password`` field is an empty string. Django treats an
empty password as *usable* (``is_password_usable("") is True``), so a guard like
``if not user.has_usable_password(): user.set_password(...)`` never fires and the
account ends up with no usable password — it can never log in. We therefore set the
password with ``set_password`` directly, guarded by ``check_password`` so re-runs
don't rewrite an already-correct hash.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.enums import UserRole
from apps.buses.models import Bus, BusStop, Route
from apps.driver_logs.enums import DriverLogEventType
from apps.driver_logs.models import DriverLog
from apps.maintenance.models import MaintenanceLog
from apps.payments.enums import PaymentGateway
from apps.payments.models import Ticket
from apps.payments.v1.service.TicketService import TicketService
from apps.payments.v1.service.WalletService import WalletService
from apps.trips.enums import TripStatus
from apps.trips.models import GpsLocation, Trip

User = get_user_model()

# One shared password for every seeded demo account — never use in production.
DEMO_PASSWORD = "Demo1234!"

# (email, role, full_name, phone) — one admin, two drivers, three passengers.
DEMO_USERS = [
    ("admin.demo@smart-transit.ai", UserRole.ADMIN, "Demo Admin", "+9779800000001"),
    ("driver.demo@smart-transit.ai", UserRole.DRIVER, "Demo Driver", "+9779800000002"),
    ("driver.two@smart-transit.ai", UserRole.DRIVER, "Sita Driver", "+9779800000003"),
    ("rider.demo@smart-transit.ai", UserRole.PASSENGER, "Demo Rider", "+9779800000004"),
    ("rider.two@smart-transit.ai", UserRole.PASSENGER, "Hari Rider", "+9779800000005"),
    ("rider.three@smart-transit.ai", UserRole.PASSENGER, "Gita Rider", "+9779800000006"),
]

# (name, color, estimated_duration_minutes, fare, [(stop_name, lat, lng), ...])
ROUTES = [
    (
        "Ring Road",
        "#1E88E5",
        55,
        "35.00",
        [
            ("Koteshwor", "27.678900", "85.347800"),
            ("Tinkune", "27.685300", "85.348900"),
            ("Maharajgunj", "27.736700", "85.331200"),
            ("Balaju", "27.730400", "85.300900"),
            ("Kalanki", "27.693600", "85.281100"),
            ("Satdobato", "27.658800", "85.325200"),
        ],
    ),
    (
        "Lagankhel–Ratnapark",
        "#E53935",
        35,
        "25.00",
        [
            ("Lagankhel", "27.667100", "85.323900"),
            ("Kupondole", "27.685800", "85.316700"),
            ("Tripureshwor", "27.694300", "85.314200"),
            ("Sundhara", "27.700600", "85.313900"),
            ("Ratnapark", "27.704700", "85.314600"),
        ],
    ),
    (
        "Bhaktapur–Kathmandu",
        "#43A047",
        50,
        "45.00",
        [
            ("Bhaktapur", "27.671000", "85.428500"),
            ("Jadibuti", "27.679800", "85.353800"),
            ("Koteshwor", "27.678900", "85.347800"),
            ("Baneshwor", "27.692000", "85.337500"),
            ("Ratnapark", "27.704700", "85.314600"),
        ],
    ),
]

# (plate, capacity, status) — drivers are assigned to these in order on creation.
BUSES = [
    ("BA 1 KHA 1001", 42, Bus.Status.ACTIVE),
    ("BA 2 KHA 2002", 36, Bus.Status.IDLE),
    ("BA 3 KHA 3003", 50, Bus.Status.MAINTENANCE),
]

# Store-credit topped onto every demo passenger's wallet on first seed (covers a few
# fares so a WALLET ticket purchase settles inline). Only applied to a fresh wallet.
DEMO_WALLET_BALANCE = Decimal("1000.00")

# (passenger_email, gateway) — issued against the first scheduled trip via TicketService
# so the QR token, Payment row, and (for WALLET) wallet ledger are all minted correctly.
# WALLET settles inline (Payment SUCCESS / Ticket ACTIVE); KHALTI stays PENDING/ISSUED,
# demoing an "awaiting gateway confirmation" ticket.
DEMO_TICKETS = [
    ("rider.demo@smart-transit.ai", PaymentGateway.WALLET),
    ("rider.two@smart-transit.ai", PaymentGateway.KHALTI),
]

# (bus_plate, service_type, cost, serviced_at, next_due) — the fleet's service history.
# The Ring Road bus's brake job is past due (next_due < today) so the admin KPI
# "buses due for maintenance" shows a non-zero signal out of the box.
MAINTENANCE_LOGS = [
    (
        "BA 1 KHA 1001",
        "Engine oil & filter change",
        "4500.00",
        datetime(2026, 5, 20, 9, 0),
        date(2026, 8, 20),
    ),
    (
        "BA 1 KHA 1001",
        "Brake pad replacement",
        "7800.00",
        datetime(2026, 3, 12, 10, 30),
        date(2026, 6, 1),
    ),
    (
        "BA 2 KHA 2002",
        "Tyre rotation & alignment",
        "2200.00",
        datetime(2026, 5, 28, 14, 0),
        date(2026, 9, 28),
    ),
    ("BA 3 KHA 3003", "Full workshop service", "15600.00", datetime(2026, 6, 5, 8, 0), None),
]

# (driver_index, event_type, notes, timestamp) — operational audit trail. driver_index
# maps into the seeded drivers list (0 = Demo Driver, 1 = Sita Driver). Benign events
# only: no SOS, so the demo's open-emergencies KPI starts clean.
DRIVER_LOGS = [
    (
        0,
        DriverLogEventType.NOTE,
        "Started shift — pre-trip vehicle inspection OK.",
        datetime(2026, 6, 12, 7, 30),
    ),
    (0, DriverLogEventType.FUEL, "Refueled 40L at Koteshwor pump.", datetime(2026, 6, 12, 8, 15)),
    (
        1,
        DriverLogEventType.DELAY,
        "~5 min delay at Kalanki due to traffic.",
        datetime(2026, 6, 12, 9, 5),
    ),
]

# `--live`: lay GPS breadcrumbs marching these fractions along the first leg (stop 1 → 2) of
# the promoted in-progress trip, so the live map shows a moving bus with a real GPS-based ETA
# to stop 2. Speed is above EtaService's MIN_SPEED floor so the GPS path (not schedule) is used.
LIVE_GPS_FRACTIONS = (Decimal("0.15"), Decimal("0.30"), Decimal("0.45"))
LIVE_GPS_SPEED = Decimal("24.00")
_SIX_DP = Decimal("0.000001")


class Command(BaseCommand):
    help = "Seed demo users (all roles), routes, stops, and buses (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--live",
            action="store_true",
            help=(
                "Also promote one scheduled trip to in-progress and lay a short GPS trail, "
                "so the live map has a moving bus with a GPS-based ETA. Idempotent."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        users_created, users_by_email = self._seed_users()
        # Insertion order mirrors DEMO_USERS, so driver indices stay stable across runs.
        drivers = [u for u in users_by_email.values() if u.role == UserRole.DRIVER]
        passengers = [u for u in users_by_email.values() if u.role == UserRole.PASSENGER]

        route_count, stop_count = self._seed_routes()
        bus_count = self._seed_buses(drivers)
        trip_count = self._seed_trips()
        wallet_count = self._seed_wallets(passengers)
        ticket_count = self._seed_tickets(users_by_email)
        maint_count = self._seed_maintenance()
        log_count = self._seed_driver_logs(drivers)
        gps_count = self._seed_live_trip() if options.get("live") else 0

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: +{users_created} users, +{route_count} routes, "
                f"+{stop_count} stops, +{bus_count} buses, +{trip_count} trips, "
                f"+{wallet_count} wallets, +{ticket_count} tickets, "
                f"+{maint_count} maintenance logs, +{log_count} driver logs"
                + (f", +{gps_count} live GPS points" if options.get("live") else "")
                + ". (Existing rows left untouched — safe to re-run.)"
            )
        )
        self.stdout.write(f"\nDemo accounts (password for all: {DEMO_PASSWORD}):")
        for email, role, *_ in DEMO_USERS:
            self.stdout.write(f"  {role:<9} {email}")

    def _seed_users(self) -> tuple[int, dict]:
        created_count = 0
        users_by_email: dict = {}
        for email, role, full_name, phone in DEMO_USERS:
            user, created = self._upsert_user(email, role, full_name, phone)
            created_count += int(created)
            users_by_email[email] = user
        return created_count, users_by_email

    @staticmethod
    def _upsert_user(email: str, role, full_name: str, phone: str) -> tuple:
        is_admin = role == UserRole.ADMIN
        # Admins double as Django-admin superusers so /admin/ is usable out of the box.
        desired = {
            "full_name": full_name,
            "phone": phone,
            "role": role,
            "is_verified": True,
            "is_active": True,
            "is_deleted": False,
            "is_staff": is_admin,
            "is_superuser": is_admin,
        }
        user, created = User.objects.get_or_create(email=email, defaults=desired)

        # Converge an existing row to the intended demo state.
        changed = False
        for field, value in desired.items():
            if getattr(user, field) != value:
                setattr(user, field, value)
                changed = True

        # Set the password explicitly — get_or_create leaves it empty (see module docstring).
        # check_password keeps re-runs from rewriting an already-correct hash.
        if not user.check_password(DEMO_PASSWORD):
            user.set_password(DEMO_PASSWORD)
            changed = True

        if changed:
            user.save()
        return user, created

    def _seed_routes(self) -> tuple[int, int]:
        route_count = stop_count = 0
        for name, color, duration, fare, stops in ROUTES:
            route, created = Route.objects.get_or_create(
                name=name,
                defaults={
                    "color": color,
                    "estimated_duration": duration,
                    "fare": Decimal(fare),
                },
            )
            route_count += int(created)
            # Converge fare on an existing demo route (idempotent re-run).
            if not created and route.fare != Decimal(fare):
                route.fare = Decimal(fare)
                route.save(update_fields=["fare", "updated_at"])
            for sequence, (stop_name, lat, lng) in enumerate(stops, start=1):
                _, s_created = BusStop.objects.get_or_create(
                    route=route,
                    sequence=sequence,
                    defaults={"name": stop_name, "lat": Decimal(lat), "lng": Decimal(lng)},
                )
                stop_count += int(s_created)
        return route_count, stop_count

    @staticmethod
    def _seed_buses(drivers: list) -> int:
        bus_count = 0
        for index, (plate, capacity, bus_status) in enumerate(BUSES):
            # Assign the demo drivers to the first buses (one each); the rest go unassigned.
            assigned = drivers[index] if index < len(drivers) else None
            _, b_created = Bus.objects.get_or_create(
                plate=plate,
                defaults={
                    "capacity": capacity,
                    "status": bus_status,
                    "assigned_driver": assigned,
                },
            )
            bus_count += int(b_created)
        return bus_count

    @staticmethod
    def _seed_trips() -> int:
        # Two scheduled demo trips: pair driver-assigned buses with existing routes.
        # driver = bus.assigned_driver, so the trip's driver matches the bus crew.
        driver_buses = list(Bus.objects.filter(assigned_driver__isnull=False).order_by("plate")[:2])
        routes = list(Route.objects.order_by("name")[:2])

        trip_count = 0
        for bus, route in zip(driver_buses, routes, strict=False):
            _, t_created = Trip.objects.get_or_create(
                bus=bus,
                route=route,
                defaults={
                    "driver": bus.assigned_driver,
                    "status": TripStatus.SCHEDULED,
                },
            )
            trip_count += int(t_created)
        return trip_count

    @staticmethod
    def _seed_wallets(passengers: list) -> int:
        # Top up only a *fresh* wallet (no ledger history). A wallet that already has
        # transactions — e.g. debited by a prior run's WALLET ticket — is left untouched
        # so re-runs don't keep re-crediting. Goes through WalletService so the balance
        # and ledger row move together under the same lock as production.
        credited = 0
        for passenger in passengers:
            wallet = WalletService.get_or_create(passenger)
            if not wallet.transactions.exists():
                WalletService.credit(wallet, DEMO_WALLET_BALANCE, reference="seed:initial-topup")
                credited += 1
        return credited

    @staticmethod
    def _seed_tickets(users_by_email: dict) -> int:
        # Issue against the first scheduled trip via TicketService, so the QR token,
        # Payment row, and (for WALLET) the wallet debit are minted exactly as in the app.
        # Idempotent guard: skip a passenger who already holds any ticket. Requires wallets
        # to be seeded first (a WALLET purchase debits store credit).
        trip = Trip.objects.filter(status=TripStatus.SCHEDULED).order_by("id").first()
        if trip is None:
            return 0
        created = 0
        for email, gateway in DEMO_TICKETS:
            passenger = users_by_email.get(email)
            if passenger is None or Ticket.objects.filter(passenger=passenger).exists():
                continue
            TicketService.issue_ticket(passenger, trip, gateway)
            created += 1
        return created

    @staticmethod
    def _seed_maintenance() -> int:
        buses = {bus.plate: bus for bus in Bus.objects.all()}
        count = 0
        for plate, service_type, cost, serviced_at, next_due in MAINTENANCE_LOGS:
            bus = buses.get(plate)
            if bus is None:
                continue
            # Keyed on (bus, service_type, serviced_at): the aware serviced_at is
            # deterministic (UTC), so re-runs match the existing row instead of duplicating.
            _, m_created = MaintenanceLog.objects.get_or_create(
                bus=bus,
                service_type=service_type,
                serviced_at=timezone.make_aware(serviced_at),
                defaults={"cost": Decimal(cost), "next_due": next_due},
            )
            count += int(m_created)
        return count

    @staticmethod
    def _seed_driver_logs(drivers: list) -> int:
        count = 0
        for driver_index, event_type, notes, ts in DRIVER_LOGS:
            if driver_index >= len(drivers):
                continue
            _, l_created = DriverLog.objects.get_or_create(
                driver=drivers[driver_index],
                event_type=event_type,
                timestamp=timezone.make_aware(ts),
                defaults={"notes": notes},
            )
            count += int(l_created)
        return count

    @staticmethod
    def _seed_live_trip() -> int:
        """Promote one trip to in-progress and lay a GPS trail between its first two stops.

        Makes the live map show a moving bus with a real GPS-based ETA (to stop 2), instead
        of the schedule-only fallback the plain seed produces. Idempotent: the trip flips to
        in_progress once (start_time set once), and the breadcrumbs use fixed timestamps so a
        re-run matches the existing rows via ``get_or_create`` rather than duplicating them.
        """
        trip = (
            Trip.objects.filter(status=TripStatus.SCHEDULED).order_by("id").first()
            or Trip.objects.filter(status=TripStatus.IN_PROGRESS).order_by("id").first()
        )
        if trip is None:
            return 0

        update_fields = []
        if trip.status != TripStatus.IN_PROGRESS:
            trip.status = TripStatus.IN_PROGRESS
            update_fields.append("status")
        if trip.start_time is None:
            trip.start_time = timezone.now()
            update_fields.append("start_time")
        if update_fields:
            trip.save(update_fields=[*update_fields, "updated_at"])

        stops = list(trip.route.stops.order_by("sequence")[:2])
        if len(stops) < 2:
            return 0
        origin, nxt = stops
        base_ts = datetime(2026, 6, 12, 9, 0)  # fixed → idempotent get_or_create on (trip, ts)
        created = 0
        for i, fraction in enumerate(LIVE_GPS_FRACTIONS):
            lat = (origin.lat + (nxt.lat - origin.lat) * fraction).quantize(_SIX_DP)
            lng = (origin.lng + (nxt.lng - origin.lng) * fraction).quantize(_SIX_DP)
            _, c = GpsLocation.objects.get_or_create(
                trip=trip,
                timestamp=timezone.make_aware(base_ts + timedelta(seconds=i * 30)),
                defaults={
                    "lat": lat,
                    "lng": lng,
                    "speed": LIVE_GPS_SPEED,
                    "heading": Decimal("45.00"),
                },
            )
            created += int(c)
        return created
