from rest_framework.views import exception_handler
from rest_framework.response import Response
from django.utils import timezone


def dms_exception_handler(exc, context):
    """
    Custom exception handler to format all DRF API exceptions
    into the standardized DMS error response structure.
    """
    response = exception_handler(exc, context)
    if response is not None:
        err_details = response.data
        message = "An error occurred."

        if isinstance(err_details, dict):
            if "detail" in err_details:
                message = err_details.pop("detail")
            elif err_details:
                # Format validation errors or other dictionary keys
                first_key = list(err_details.keys())[0]
                first_val = err_details[first_key]
                if isinstance(first_val, list):
                    first_val = ", ".join(str(v) for v in first_val)
                message = f"{first_key}: {first_val}"
        elif isinstance(err_details, list):
            message = ", ".join(str(item) for item in err_details)

        # Standardize structure
        response.data = {
            "status": "error",
            "data": None,
            "meta": {
                "version": "1.0",
                "timestamp": timezone.now().isoformat(),
            },
            "error": {
                "code": getattr(exc, "default_code", "api_error"),
                "message": str(message),
                "details": (
                    err_details
                    if isinstance(err_details, dict)
                    else {"non_field_errors": err_details}
                ),
            },
        }
    return response
