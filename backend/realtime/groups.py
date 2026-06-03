"""Channel-layer group-name helpers.

Centralised so consumers and producers (REST services, Celery tasks) agree on the
exact string and never drift. A group name is just a routing key into the Redis
channel layer; getting one character wrong silently breaks fan-out, so nobody
should hand-write these literals.
"""

# Static groups (one per role-wide stream).
FLEET = "fleet"
ALERTS = "alerts.admin"


def trip_group(trip_id) -> str:
    """Per-trip group: every passenger watching this bus plus its driver."""
    return f"trip.{trip_id}"


def notifications_group(user_id) -> str:
    """Per-user in-app notification stream."""
    return f"notifications.{user_id}"
