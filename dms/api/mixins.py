from rest_framework import status
from rest_framework.response import Response

from dms.api_contract import build_error_payload, build_success_payload


class StandardAPIResponseMixin:
    """
    Mixin to standardize API responses in DMS.
    """

    def success_response(
        self, data, meta=None, status_code=status.HTTP_200_OK
    ) -> Response:
        payload = build_success_payload(
            request=self.request,
            data=data,
            meta_extra=meta,
        )
        return Response(payload, status=status_code)

    def error_response(
        self,
        message,
        code="api_error",
        details=None,
        status_code=status.HTTP_400_BAD_REQUEST,
    ) -> Response:
        payload = build_error_payload(
            request=self.request,
            code=code,
            message=message,
            details=details,
        )
        return Response(payload, status=status_code)
