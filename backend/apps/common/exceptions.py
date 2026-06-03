"""Custom DRF exception handler that produces the ``errors`` envelope.

Converts DRF's varied error shapes (field dicts, ``{"detail": ...}``, lists) into
a flat list of ``{code, field, detail}`` objects with stable machine-readable
codes the frontend can branch on.
"""

from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler


class CustomException(APIException):
    """Domain exception raised by the service layer.

    A subclass of DRF's ``APIException`` so the standard exception handler picks it up
    and ``status`` flows through. Carry an optional pre-built ``errors`` list (each
    ``{code, field, detail}``) when a service wants to emit structured field errors;
    otherwise the ``message`` becomes a single error entry.
    """

    status_code = 400
    default_detail = "A business rule was violated."
    default_code = "error"

    def __init__(self, message=None, status=None, errors=None, code=None):
        if status is not None:
            self.status_code = status
        self.errors = errors
        super().__init__(detail=message or self.default_detail, code=code or self.default_code)


def envelope_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        # Unhandled exception -> let Django produce a 500 (no internals leaked).
        return None

    if isinstance(exc, CustomException) and exc.errors is not None:
        # Service supplied a ready-made error list (or a field dict to flatten).
        errors = exc.errors if isinstance(exc.errors, list) else _normalize(exc.errors)
    else:
        errors = _normalize(response.data)

    response.data = {
        "data": None,
        "meta": None,
        "errors": errors,
        "__enveloped_error__": True,  # signals the renderer to pass through
    }
    return response


def _normalize(data) -> list[dict]:
    errors: list[dict] = []
    if isinstance(data, dict):
        for field, detail in data.items():
            if isinstance(detail, (list, tuple)):
                errors.extend(_make(field, d) for d in detail)
            elif isinstance(detail, dict):
                # Nested serializer errors -> flatten with dotted field path.
                for sub_field, sub_detail in detail.items():
                    subs = sub_detail if isinstance(sub_detail, (list, tuple)) else [sub_detail]
                    errors.extend(_make(f"{field}.{sub_field}", d) for d in subs)
            else:
                errors.append(_make(field, detail))
    elif isinstance(data, (list, tuple)):
        errors.extend(_make(None, d) for d in data)
    else:
        errors.append(_make(None, data))
    return errors


def _make(field, detail) -> dict:
    # DRF ErrorDetail carries a machine code (e.g. "invalid", "required").
    code = getattr(detail, "code", None) or "error"
    # Generic buckets aren't useful as a field name.
    field_name = None if field in (None, "detail", "non_field_errors") else field
    return {"code": code, "field": field_name, "detail": str(detail)}
