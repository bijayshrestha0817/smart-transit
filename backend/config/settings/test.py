"""Test settings — in-memory SQLite + locmem so the suite runs without
Postgres/Redis. SQLite is acceptable for P0 auth tests; integration tests that
exercise Postgres-specific behaviour run against Postgres in CI/Docker.
"""

from .base import *  # noqa: F401,F403

DEBUG = False

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# Fast hashing for tests (never use in prod).
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

JWT_AUTH_COOKIE_SECURE = False
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Run Celery tasks inline (synchronously) so async delivery is exercised + asserted
# in tests without a broker/worker, and surface task exceptions to the caller.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
