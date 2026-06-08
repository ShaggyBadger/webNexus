from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.utils import timezone


class DMSSerializedPagination(PageNumberPagination):
    """
    Custom pagination class matching the DMS standardized response format.
    """

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response(
            {
                "status": "success",
                "data": data,
                "meta": {
                    "version": "1.0",
                    "timestamp": timezone.now().isoformat(),
                    "pagination": {
                        "count": self.page.paginator.count,
                        "next": self.get_next_link(),
                        "prev": self.get_previous_link(),
                    },
                },
                "error": None,
            }
        )
