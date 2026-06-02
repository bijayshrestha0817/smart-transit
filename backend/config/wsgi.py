"""WSGI entrypoint — used by Gunicorn for the synchronous HTTP/DRF process."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_wsgi_application()
