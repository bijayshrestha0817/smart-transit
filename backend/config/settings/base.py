"""
Base settings shared across all environments.

Environment-specific modules (dev/prod/test) import * from here and override.
Configuration is read from environment variables via django-environ; see
``backend/.env.example`` for the full list.
"""

from datetime import timedelta
from pathlib import Path

import environ

# backend/ — three parents up from config/settings/base.py
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_SECRET_KEY=(str, "dev-insecure-secret-change-me-0123456789-abcdef-ghij"),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1", "[::1]"]),
    DATABASE_URL=(str, "postgres://postgres:postgres@localhost:5432/smart_transit"),
    REDIS_URL=(str, "redis://localhost:6379/0"),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:3000"]),
    CSRF_TRUSTED_ORIGINS=(list, ["http://localhost:3000"]),
    JWT_COOKIE_SECURE=(bool, False),
    FRONTEND_URL=(str, "http://localhost:3000"),
)

# Load .env if present (no-op in containers that inject real env vars).
environ.Env.read_env(BASE_DIR / ".env")

# ── Core ─────────────────────────────────────────────────────────────────────
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "daphne",  # ASGI server; must precede staticfiles so runserver uses ASGI
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "django_filters",
    "corsheaders",
    "channels",
    # Local
    "apps.common",
    "apps.accounts",
    "apps.buses",
    "apps.trips",
    "apps.payments",
    "apps.notifications",
    "apps.driver_logs",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ── Auth ─────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"

# Argon2 first (most secure), PBKDF2 as fallback for legacy hashes.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── Database ─────────────────────────────────────────────────────────────────
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"].setdefault("CONN_MAX_AGE", 60)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Redis: cache + channel layer + Celery broker ─────────────────────────────
REDIS_URL = env("REDIS_URL")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

# ── Celery ───────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 270
CELERY_BEAT_SCHEDULE: dict = {}  # populated in P5 (anomaly poll, nightly maintenance)

# ── DRF ──────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("apps.accounts.authentication.CookieJWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": ("apps.common.renderers.EnvelopeJSONRenderer",),
    "EXCEPTION_HANDLER": "apps.common.exceptions.envelope_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.DefaultCursorPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/min",
        "passenger": "100/min",
        "driver": "300/min",
        "admin": "500/min",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# ── SimpleJWT: 15m access / 7d refresh, rotation + blacklist ─────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# Cookie delivery for JWTs — HttpOnly so client JS can never read tokens.
JWT_AUTH_COOKIE = "st_access"
JWT_AUTH_REFRESH_COOKIE = "st_refresh"
JWT_AUTH_COOKIE_HTTPONLY = True
JWT_AUTH_COOKIE_SAMESITE = "Strict"
JWT_AUTH_COOKIE_SECURE = env("JWT_COOKIE_SECURE")  # True in prod (HTTPS)
JWT_AUTH_COOKIE_PATH = "/"

# ── drf-spectacular ──────────────────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    "TITLE": "Smart Transit AI API",
    "DESCRIPTION": "Intelligent public-transportation platform — REST + WebSocket API.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/v1",
    # Several models expose a ``status`` choice field; name each enum component
    # explicitly so drf-spectacular doesn't fall back to hashed "StatusXyzEnum" names.
    "ENUM_NAME_OVERRIDES": {
        "BusStatusEnum": "apps.buses.enums.BusStatus.choices",
        "TripStatusEnum": "apps.trips.enums.TripStatus.choices",
        "TicketStatusEnum": "apps.payments.enums.TicketStatus.choices",
        "PaymentGatewayEnum": "apps.payments.enums.PaymentGateway.choices",
        "PaymentStatusEnum": "apps.payments.enums.PaymentStatus.choices",
        "WalletTxnKindEnum": "apps.payments.enums.WalletTxnKind.choices",
        "NotificationTypeEnum": "apps.notifications.enums.NotificationType.choices",
        "DriverLogEventTypeEnum": "apps.driver_logs.enums.DriverLogEventType.choices",
    },
}

# ── CORS / CSRF ──────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True  # required so the browser sends auth cookies
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")
CSRF_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_SAMESITE = "Strict"

# ── I18N / TZ ────────────────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
CELERY_TIMEZONE = TIME_ZONE

# ── Static / media ───────────────────────────────────────────────────────────
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

# ── Email (console in dev; SMTP in prod via env) ─────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "Smart Transit AI <no-reply@smart-transit.ai>"
FRONTEND_URL = env("FRONTEND_URL")

# ── Logging ──────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{levelname}] {asctime} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
