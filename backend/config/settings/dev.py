"""Development settings — verbose, browsable, insecure cookies over HTTP."""

from .base import *  # noqa: F401,F403
from .base import REST_FRAMEWORK

DEBUG = True

# Enable the DRF browsable API alongside the JSON envelope while developing.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": (
        "apps.common.renderers.EnvelopeJSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
}
