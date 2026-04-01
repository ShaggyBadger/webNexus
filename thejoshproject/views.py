from django.http import JsonResponse
from django.db import connection
import time


def health_check(request):
    """
    Tactical Health Check: Verifies DB connectivity and returns system status.
    """
    status = {"db_status": "OFFLINE", "timestamp": time.time()}

    try:
        # Perform a simple query to verify DB connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        status["db_status"] = "SYNC_OK"
    except Exception as e:
        status["db_status"] = "ERROR"
        status["error_details"] = str(e)

    return JsonResponse(status)
