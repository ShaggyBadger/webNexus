from rest_framework.response import Response


def get_trace_id(request):
    return (
        request.META.get("HTTP_X_TRACE_ID")
        or request.META.get("HTTP_X_REQUEST_ID")
        or request.META.get("REQUEST_ID")
    )


def drf_success_response(*, data, status_code=200):
    return Response({"status": "success", "data": data}, status=status_code)


def drf_error_response(*, request, code, message, status_code, details=None):
    return Response(
        {
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
                "trace_id": get_trace_id(request),
            }
        },
        status=status_code,
    )
