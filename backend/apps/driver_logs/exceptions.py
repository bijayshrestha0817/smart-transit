"""Domain exceptions for the driver_logs app (build on the shared CustomException)."""

from apps.common.exceptions import CustomException


class InvalidTripForLogError(CustomException):
    def __init__(self):
        super().__init__(
            message="This trip is not yours or does not exist.",
            status=400,
            code="invalid_trip",
        )
