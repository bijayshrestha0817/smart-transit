"""Domain exceptions for the accounts app (build on the shared CustomException)."""

from apps.common.exceptions import CustomException


class InvalidCredentialsError(CustomException):
    def __init__(self):
        super().__init__(
            message="Invalid email or password.", status=400, code="invalid_credentials"
        )


class EmailNotVerifiedError(CustomException):
    def __init__(self):
        super().__init__(
            message="Please verify your email before logging in.",
            status=400,
            code="not_verified",
        )
