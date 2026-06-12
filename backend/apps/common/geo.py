"""Small, dependency-free geo helpers shared across apps.

``haversine_km`` is the true great-circle distance between two lat/lng points — the
complement to ``BusStopRepository.nearby``'s bounding-box filter (which trades exactness
for an index-friendly range query). Inputs may be ``float``, ``str``, or ``Decimal`` (GPS
and stop coordinates are ``DecimalField`` on the wire); everything is coerced to float for
the trig. No PostGIS, so this runs identically on SQLite (tests) and Postgres (prod).
"""

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0088  # mean Earth radius (IUGG)


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    """Great-circle distance between two points in kilometres.

    Accepts numeric or string/Decimal coordinates. Returns 0.0 for identical points.
    """
    lat1_f, lng1_f, lat2_f, lng2_f = (float(lat1), float(lng1), float(lat2), float(lng2))
    d_lat = radians(lat2_f - lat1_f)
    d_lng = radians(lng2_f - lng1_f)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1_f)) * cos(radians(lat2_f)) * sin(d_lng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))
