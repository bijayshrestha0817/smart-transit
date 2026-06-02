"""Pagination.

Cursor pagination is the default (stable under inserts, good for live data). An
offset variant is available for views that opt in (e.g. admin tables wanting
jump-to-page). Both tag their payload with ``__paginated__`` so the envelope
renderer can lift ``results``/``pagination`` into ``data``/``meta``.
"""

from rest_framework.pagination import CursorPagination, PageNumberPagination
from rest_framework.response import Response


class DefaultCursorPagination(CursorPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-created_at"

    def get_paginated_response(self, data) -> Response:
        return Response(
            {
                "__paginated__": True,
                "results": data,
                "pagination": {
                    "next": self.get_next_link(),
                    "prev": self.get_previous_link(),
                    "page_size": self.get_page_size(self.request) or self.page_size,
                },
            }
        )


class OffsetFallbackPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data) -> Response:
        return Response(
            {
                "__paginated__": True,
                "results": data,
                "pagination": {
                    "next": self.get_next_link(),
                    "prev": self.get_previous_link(),
                    "count": self.page.paginator.count,
                    "page_size": self.get_page_size(self.request) or self.page_size,
                },
            }
        )
