"""Idempotent demo seed: Kathmandu-area routes, ordered stops, and a small fleet.

Safe to run repeatedly — every object is created via ``get_or_create`` keyed on a
natural identifier, so a second run is a no-op. Run with::

    DJANGO_SETTINGS_MODULE=config.settings.dev python manage.py seed_demo
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.buses.models import Bus, BusStop, Route

User = get_user_model()

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

# (plate, capacity, status, route_index_for_driver_assignment_or_None)
BUSES = [
    ("BA 1 KHA 1001", 42, Bus.Status.ACTIVE),
    ("BA 2 KHA 2002", 36, Bus.Status.IDLE),
    ("BA 3 KHA 3003", 50, Bus.Status.MAINTENANCE),
]


class Command(BaseCommand):
    help = "Seed demo routes, stops, buses, and a driver (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        driver, _ = User.objects.get_or_create(
            email="driver.demo@smart-transit.ai",
            defaults={"full_name": "Demo Driver", "phone": "+9779800000000"},
        )
        # Ensure the demo driver is a verified driver with a usable password.
        changed = False
        if driver.role != User.Roles.DRIVER:
            driver.role = User.Roles.DRIVER
            changed = True
        if not driver.is_verified:
            driver.is_verified = True
            changed = True
        if not driver.has_usable_password():
            driver.set_password("DemoDriver123!")
            changed = True
        if changed:
            driver.save()

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
                    defaults={
                        "name": stop_name,
                        "lat": Decimal(lat),
                        "lng": Decimal(lng),
                    },
                )
                stop_count += int(s_created)

        bus_count = 0
        for index, (plate, capacity, bus_status) in enumerate(BUSES):
            _, b_created = Bus.objects.get_or_create(
                plate=plate,
                defaults={
                    "capacity": capacity,
                    "status": bus_status,
                    # Assign the demo driver to the first (active) bus only.
                    "assigned_driver": driver if index == 0 else None,
                },
            )
            bus_count += int(b_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: +{route_count} routes, +{stop_count} stops, "
                f"+{bus_count} buses, driver={driver.email}. "
                "(Existing rows left untouched — safe to re-run.)"
            )
        )
