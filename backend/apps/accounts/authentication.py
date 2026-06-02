"""JWT authentication that accepts the token from the HttpOnly cookie.

Browser clients never see the token (it's HttpOnly), so they can't send an
Authorization header — the cookie carries it. Non-browser clients (mobile,
service-to-service) can still use the standard ``Authorization: Bearer`` header.
This is also the class P2's WebSocket middleware reuses to validate the handshake.
"""

from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        if header is not None:
            raw_token = self.get_raw_token(header)
        else:
            raw_token = request.COOKIES.get(settings.JWT_AUTH_COOKIE)

        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token
