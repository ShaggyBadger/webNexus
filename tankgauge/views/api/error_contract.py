from django.http import JsonResponse
from rest_framework.response import Response


def get_trace_id(request) -> str | None:
    return (
        request.META.get("HTTP_X_TRACE_ID")
        or request.META.get("HTTP_X_REQUEST_ID")
        or request.META.get("REQUEST_ID")
    )


def build_error_payload(
    *,
    request,
    code: str,
    message: str,
    details=None,
):
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "trace_id": get_trace_id(request),
        }
    }


def build_success_payload(*, data):
    return {"status": "success", "data": data}


def drf_error_response(
    *,
    request,
    code: str,
    message: str,
    status_code: int,
    details=None,
) -> Response:
    return Response(
        build_error_payload(
            request=request,
            code=code,
            message=message,
            details=details,
        ),
        status=status_code,
    )


def json_error_response(
    *,
    request,
    code: str,
    message: str,
    status_code: int,
    details=None,
) -> JsonResponse:
    return JsonResponse(
        build_error_payload(
            request=request,
            code=code,
            message=message,
            details=details,
        ),
        status=status_code,
    )


def drf_success_response(*, data, status_code: int = 200) -> Response:
    return Response(build_success_payload(data=data), status=status_code)


def json_success_response(*, data, status_code: int = 200) -> JsonResponse:
    return JsonResponse(build_success_payload(data=data), status=status_code)


def flatten_serializer_errors(errors) -> str:
    if isinstance(errors, dict):
        parts = []
        for field, value in errors.items():
            if isinstance(value, (list, tuple)):
                rendered = ", ".join(str(item) for item in value)
            else:
                rendered = str(value)
            parts.append(f"{field}: {rendered}")
        return " | ".join(parts)
    return str(errors)
