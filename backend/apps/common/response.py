"""CustomResponse — explicit ``{data, meta, errors}`` envelope builder.

In the layered architecture, views construct their response with ``CustomResponse``
instead of returning a bare payload and letting a renderer wrap it. The wire shape is
unchanged (``{data, meta, errors}``) so the frontend contract and existing tests stay
stable — only the *mechanism* moves from implicit (renderer) to explicit (here).

The payload is tagged ``__enveloped__`` so ``EnvelopeJSONRenderer`` passes it through
without re-wrapping. This lets already-migrated (CustomResponse) and not-yet-migrated
(plain ``Response``) views coexist during the refactor.
"""

from rest_framework.response import Response


class CustomResponse(Response):
    def __init__(self, data=None, meta=None, message=None, status=None, **kwargs):
        # A human-readable message rides in meta so the envelope keeps three top-level keys.
        if message is not None:
            meta = {**(meta or {}), "message": message}
        payload = {"data": data, "meta": meta, "errors": None, "__enveloped__": True}
        super().__init__(data=payload, status=status, **kwargs)
