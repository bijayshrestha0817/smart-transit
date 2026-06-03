"""Domain exceptions for the buses app (build on the shared CustomException)."""

from apps.common.exceptions import CustomException


class DriverNotFoundError(CustomException):
    def __init__(self):
        super().__init__(
            message="No active driver with this id.", status=404, code="invalid_driver"
        )
