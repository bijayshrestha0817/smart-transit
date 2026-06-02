"""drf-spectacular security scheme for ``CookieJWTAuthentication``.

drf-spectacular ships ``SimpleJWTScheme`` for ``JWTAuthentication`` but it does
**not** match subclasses, so our ``CookieJWTAuthentication`` is unresolved and
``/api/schema/`` emits a "could not resolve authenticator" warning. This
extension teaches the schema generator how to represent it.

The authenticator accepts the JWT from **either** the HttpOnly access cookie
(browser clients) **or** a standard ``Authorization: Bearer`` header
(mobile / service-to-service), so the two are modelled as *alternative* security
requirements (cookie OR bearer), not both-required.

Registered at app load via ``AccountsConfig.ready()`` so it's present before any
schema generation.
"""

from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.plumbing import build_bearer_security_scheme_object


class CookieJWTScheme(OpenApiAuthenticationExtension):
    target_class = "apps.accounts.authentication.CookieJWTAuthentication"
    name = ["jwtCookieAuth", "jwtBearerAuth"]  # one component per input mode
    priority = 1  # outrank the built-in JWTAuthentication scheme if it ever matches

    def get_security_definition(self, auto_schema):
        return [
            {"type": "apiKey", "in": "cookie", "name": settings.JWT_AUTH_COOKIE},
            build_bearer_security_scheme_object(
                header_name="Authorization",
                token_prefix="Bearer",
                bearer_format="JWT",
            ),
        ]

    def get_security_requirement(self, auto_schema):
        # List of dicts => alternatives (OR): a request may authenticate with the
        # cookie or the bearer header, not necessarily both.
        return [{"jwtCookieAuth": []}, {"jwtBearerAuth": []}]
