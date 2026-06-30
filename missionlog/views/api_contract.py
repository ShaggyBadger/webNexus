from django.http import JsonResponse


def get_trace_id(request):
    return (
        request.META.get("HTTP_X_TRACE_ID")
        or request.META.get("HTTP_X_REQUEST_ID")
        or request.META.get("REQUEST_ID")
    )


def build_success_payload(*, data):
    return {"status": "success", "data": data}


def build_error_payload(*, request, code, message, details=None):
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "trace_id": get_trace_id(request),
        }
    }


def json_success_response(*, data, status_code=200):
    return JsonResponse(build_success_payload(data=data), status=status_code)


def json_error_response(*, request, code, message, status_code, details=None):
    return JsonResponse(
        build_error_payload(
            request=request,
            code=code,
            message=message,
            details=details,
        ),
        status=status_code,
    )
