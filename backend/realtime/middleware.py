"""WebSocket JWT authentication middleware.

The HTTP path authenticates via ``apps.accounts.authentication.CookieJWTAuthentication``;
this is its WebSocket counterpart. Browsers can't set an ``Authorization`` header on a
WebSocket handshake, so the access token arrives either in the ``st_access`` cookie
(``settings.JWT_AUTH_COOKIE``) or as a ``?token=`` query-string parameter. We validate it
with SimpleJWT and resolve the user from the ``user_id`` claim, mirroring the REST class.

This middleware NEVER raises: a missing/invalid/expired token resolves to
``AnonymousUser`` and the consumer decides how to close (``close(4401)``). Raising here
would surface as an opaque 500 during the handshake instead of a clean WS close code.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def _get_user(user_id):
    """Resolve the user from the JWT ``user_id`` claim.

    ``get_user_model()`` is imported lazily inside the DB-bound helper so the module
    can be imported before the app registry is ready (it is imported by ASGI wiring).
    """
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    try:
        user = user_model.objects.get(pk=user_id)
    except user_model.DoesNotExist:
        return AnonymousUser()
    # A deactivated account must not authenticate over WS either.
    if not getattr(user, "is_active", True):
        return AnonymousUser()
    return user


def _raw_token_from_scope(scope) -> str | None:
    """Pull the access token from the cookie header or the ?token= query param."""
    # 1. Cookie header — Channels delivers raw headers as a list of (name, value) byte tuples.
    cookie_name = settings.JWT_AUTH_COOKIE
    for header_name, header_value in scope.get("headers", []):
        if header_name == b"cookie":
            cookies = _parse_cookie_header(header_value.decode("latin-1"))
            if cookie_name in cookies:
                return cookies[cookie_name]

    # 2. Query string fallback (?token=...).
    query_string = scope.get("query_string", b"").decode("latin-1")
    if query_string:
        params = parse_qs(query_string)
        token = params.get("token")
        if token:
            return token[0]

    return None


def _parse_cookie_header(raw: str) -> dict[str, str]:
    """Minimal ``Cookie:`` header parser (name=value; name2=value2)."""
    cookies: dict[str, str] = {}
    for chunk in raw.split(";"):
        if "=" in chunk:
            name, value = chunk.split("=", 1)
            cookies[name.strip()] = value.strip()
    return cookies


async def _resolve_user(scope):
    raw_token = _raw_token_from_scope(scope)
    if not raw_token:
        return AnonymousUser()
    try:
        validated = AccessToken(raw_token)
    except (InvalidToken, TokenError):
        return AnonymousUser()
    user_id = validated.get(settings.SIMPLE_JWT["USER_ID_CLAIM"])
    if user_id is None:
        return AnonymousUser()
    return await _get_user(user_id)


class JWTAuthMiddleware(BaseMiddleware):
    """Populate ``scope['user']`` from a JWT on the WebSocket handshake."""

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        scope["user"] = await _resolve_user(scope)
        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):  # noqa: N802 — matches Channels' Stack naming convention
    """Convenience wrapper, mirroring ``channels.auth.AuthMiddlewareStack``."""
    return JWTAuthMiddleware(inner)
