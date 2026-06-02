"""Stateless signed tokens for email verification and password reset.

Uses Django's signing (HMAC over SECRET_KEY) so no extra DB table is needed; the
token is self-expiring via ``max_age``. Distinct salts prevent a verify token
from being replayed as a reset token.
"""

from django.core import signing

_EMAIL_VERIFY_SALT = "accounts.email-verify"
_PASSWORD_RESET_SALT = "accounts.password-reset"

EMAIL_VERIFY_MAX_AGE = 60 * 60 * 24  # 24 hours
PASSWORD_RESET_MAX_AGE = 60 * 60  # 1 hour

# Re-exported so callers can catch expiry/tamper without importing signing.
BadSignature = signing.BadSignature
SignatureExpired = signing.SignatureExpired


def make_email_verify_token(user_id: int) -> str:
    return signing.dumps({"uid": user_id}, salt=_EMAIL_VERIFY_SALT)


def read_email_verify_token(token: str) -> int:
    data = signing.loads(token, salt=_EMAIL_VERIFY_SALT, max_age=EMAIL_VERIFY_MAX_AGE)
    return int(data["uid"])


def make_password_reset_token(user_id: int) -> str:
    return signing.dumps({"uid": user_id}, salt=_PASSWORD_RESET_SALT)


def read_password_reset_token(token: str) -> int:
    data = signing.loads(token, salt=_PASSWORD_RESET_SALT, max_age=PASSWORD_RESET_MAX_AGE)
    return int(data["uid"])
