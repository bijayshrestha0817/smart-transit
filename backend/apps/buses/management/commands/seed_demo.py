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

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.enums import UserRole
from apps.buses.models import Bus, BusStop, Route
from apps.trips.enums import TripStatus
from apps.trips.models import Trip

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

# (name, color, estimated_duration_minutes, [(stop_name, lat, lng), ...])
ROUTES = [
    (
        "Ring Road",
        "#1E88E5",
        55,
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


class Command(BaseCommand):
    help = "Seed demo users (all roles), routes, stops, and buses (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        users_created, drivers = self._seed_users()
        route_count, stop_count = self._seed_routes()
        bus_count = self._seed_buses(drivers)
        trip_count = self._seed_trips()

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: +{users_created} users, +{route_count} routes, "
                f"+{stop_count} stops, +{bus_count} buses, +{trip_count} trips. "
                "(Existing rows left untouched — safe to re-run.)"
            )
        )
        self.stdout.write(f"\nDemo accounts (password for all: {DEMO_PASSWORD}):")
        for email, role, *_ in DEMO_USERS:
            self.stdout.write(f"  {role:<9} {email}")

    def _seed_users(self) -> tuple[int, list]:
        created_count = 0
        drivers: list = []
        for email, role, full_name, phone in DEMO_USERS:
            user, created = self._upsert_user(email, role, full_name, phone)
            created_count += int(created)
            if role == UserRole.DRIVER:
                drivers.append(user)
        return created_count, drivers

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
        for name, color, duration, stops in ROUTES:
            route, created = Route.objects.get_or_create(
                name=name,
                defaults={"color": color, "estimated_duration": duration},
            )
            route_count += int(created)
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
