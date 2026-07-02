from django.utils import timezone


def get_trace_id(request) -> str | None:
    if request is None:
        return None
    return (
        request.META.get("HTTP_X_TRACE_ID")
        or request.META.get("HTTP_X_REQUEST_ID")
        or request.META.get("REQUEST_ID")
    )


def build_meta(*, request, extra: dict | None = None) -> dict:
    meta = {
        "version": "1.1",
        "timestamp": timezone.now().isoformat(),
        "trace_id": get_trace_id(request),
    }
    if extra:
        meta.update(extra)
    return meta


def build_success_payload(*, request, data, meta_extra: dict | None = None) -> dict:
    return {
        "status": "success",
        "data": data,
        "meta": build_meta(request=request, extra=meta_extra),
        "error": None,
    }


def build_error_payload(
    *, request, code: str, message: str, details: dict | None = None
) -> dict:
    return {
        "status": "error",
        "data": None,
        "meta": build_meta(request=request),
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "trace_id": get_trace_id(request),
        },
    }
