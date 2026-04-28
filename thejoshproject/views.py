import logging
import time
from django.http import JsonResponse
from django.db import connection

# Tactical Logger
logger = logging.getLogger('django.server')

def health_check(request):
    """
    TACTICAL_SYSTEM_STATUS:
    Verifies core infrastructure availability.
    Checks database heartbeat and system latency.
    """
    status = {"status": "OPERATIONAL", "db_status": "OFFLINE", "timestamp": time.time()}

    try:
        # DB_HEARTBEAT: Perform a minimal query to verify connectivity.
        start_time = time.time()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        latency = (time.time() - start_time) * 1000
        
        status["db_status"] = "DB_READY"
        status["latency_ms"] = f"{latency:.2f}"
        logger.debug(f"HEALTH_CHECK: System operational. DB Latency: {latency:.2f}ms")
    except Exception as e:
        status["status"] = "CRITICAL"
        status["db_status"] = "ERROR"
        status["error_details"] = str(e)
        logger.error(f"HEALTH_CHECK_FAILURE: Database heartbeat failed: {str(e)}")

    return JsonResponse(status)
