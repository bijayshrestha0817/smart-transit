"""Domain exceptions for the trips app (build on the shared CustomException)."""

from apps.common.exceptions import CustomException


class TripAlreadyStartedError(CustomException):
    def __init__(self):
        super().__init__(
            message="This trip has already been started.",
            status=409,
            code="trip_already_started",
        )


class TripNotInProgressError(CustomException):
    def __init__(self):
        super().__init__(
            message="This trip is not in progress.",
            status=409,
            code="trip_not_in_progress",
        )


class TripNotAssignedError(CustomException):
    def __init__(self):
        super().__init__(
            message="You are not the driver assigned to this trip.",
            status=403,
            code="trip_not_assigned",
        )
