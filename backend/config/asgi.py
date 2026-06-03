"""ASGI entrypoint. Routes HTTP to Django and WebSocket to Channels.

The WebSocket router and the JWT-on-connect middleware live in the top-level
``realtime/`` package (NOT ``channels/`` — a local package by that name would shadow
the installed ``channels`` library and break ASGI boot). Channels imports happen AFTER
``get_asgi_application()`` so the app registry is ready first.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

# Initialise Django before importing anything that touches the app registry.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

import realtime.routing  # noqa: E402
from realtime.middleware import JWTAuthMiddleware  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            JWTAuthMiddleware(URLRouter(realtime.routing.websocket_urlpatterns))
        ),
    }
)
