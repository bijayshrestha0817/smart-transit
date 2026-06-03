"""Response envelope renderer.

Every response is shaped as ``{data, meta, errors}``:

* success (single)     -> {"data": <obj>,   "meta": null, "errors": null}
* success (paginated)  -> {"data": [...],   "meta": {"pagination": {...}}, "errors": null}
* error                -> {"data": null,    "meta": null, "errors": [ {...} ]}

Paginated payloads are tagged by ``DefaultCursorPagination`` and error payloads
by ``envelope_exception_handler`` (see exceptions.py) so this renderer never has
to guess what it's wrapping.
"""

from rest_framework.renderers import JSONRenderer


class EnvelopeJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get("response")

        if isinstance(data, dict) and data.pop("__enveloped_error__", False):
            # Already shaped by the exception handler.
            payload = data
        elif isinstance(data, dict) and data.pop("__enveloped__", False):
            # Already shaped by CustomResponse — pass through untouched.
            payload = data
        elif isinstance(data, dict) and data.pop("__paginated__", False):
            payload = {
                "data": data["results"],
                "meta": {"pagination": data["pagination"]},
                "errors": None,
            }
        elif response is not None and response.status_code >= 400:
            # Error that bypassed the handler (rare) — wrap defensively.
            payload = {"data": None, "meta": None, "errors": _as_error_list(data)}
        else:
            payload = {"data": data, "meta": None, "errors": None}

        return super().render(payload, accepted_media_type, renderer_context)


def _as_error_list(data):
    if isinstance(data, dict) and "errors" in data:
        return data["errors"]
    return [{"code": "error", "field": None, "detail": str(data)}]
