"""
ASGI entrypoint. Routes HTTP to Django and WebSocket to Channels.

The WebSocket URL patterns and the JWT-on-connect middleware are added in P2
(see backend/channels/). For now the websocket router is empty but wired, so the
process boots as a full ASGI app and P2 only needs to register patterns.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

# Initialise Django before importing anything that touches the app registry.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

# P2 will populate this from backend/channels/routing.py.
websocket_urlpatterns: list = []

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(URLRouter(websocket_urlpatterns)),
    }
)
