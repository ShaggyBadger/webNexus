import logging
import threading
import json
import datetime

# Thread-local storage to hold request-specific metadata for tactical logging
_thread_locals = threading.local()
logger = logging.getLogger('django.server')

def get_current_request_meta():
    """
    TACTICAL_INTEL:
    Retrieves request metadata from the current thread's storage.
    Used by filters and formatters to inject context into logs.
    """
    return {
        'ip': getattr(_thread_locals, 'ip', '0.0.0.0'),
        'ua': getattr(_thread_locals, 'ua', 'UNKNOWN_UA'),
        'method': getattr(_thread_locals, 'method', 'UNKNOWN_METHOD'),
        'path': getattr(_thread_locals, 'path', 'UNKNOWN_PATH'),
        'user': getattr(_thread_locals, 'user', 'ANONYMOUS'),
        'referrer': getattr(_thread_locals, 'referrer', 'NO_REFERRER')
    }

class LoggingMiddleware:
    """
    TACTICAL_TELEMETRY_MIDDLEWARE:
    Captures comprehensive request metadata (IP, UA, Method, Path, User) 
    and stores it in thread-local storage for use by the logging system.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        logger.info("SYSTEM_TELEMETRY: LoggingMiddleware initialized.")

    def __call__(self, request):
        # 1. Capture IP (Handling Nginx/Proxy with X-Forwarded-For)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')

        # 2. Capture User and Metadata (Safe check for request.user)
        _thread_locals.ip = ip
        _thread_locals.ua = request.META.get('HTTP_USER_AGENT', 'UNKNOWN_UA')
        _thread_locals.method = request.method
        _thread_locals.path = request.path
        
        # Safety catch: request.user only exists after AuthenticationMiddleware
        user = getattr(request, 'user', None)
        _thread_locals.user = user.username if user and user.is_authenticated else "ANONYMOUS"
        
        _thread_locals.referrer = request.META.get('HTTP_REFERER', 'NO_REFERRER')

        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        """
        Captured when a view or template rendering raises an uncaught exception.
        """
        logger = logging.getLogger('django.request')
        meta = get_current_request_meta()
        logger.error(
            f"SERVER_CRITICAL: {type(exception).__name__} - {str(exception)}",
            exc_info=True,
            extra=meta
        )
        return None

class TacticalFilter(logging.Filter):
    """
    Logging filter that injects all captured request metadata into the log record.
    """
    def filter(self, record):
        meta = get_current_request_meta()
        for key, value in meta.items():
            setattr(record, key, value)
        return True

class TacticalJSONEncoder(json.JSONEncoder):
    """
    TACTICAL_ENCODER:
    Handles non-serializable objects (like sockets, datetimes, or complex objects)
    by converting them to their string representation.
    """
    def default(self, obj):
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)

class TacticalJSONMinimalFormatter(logging.Formatter):
    """
    Clean, high-level JSON log formatter (Timestamp, Level, IP, Message).
    """
    def format(self, record):
        timestamp = datetime.datetime.fromtimestamp(record.created, datetime.timezone.utc).isoformat()
        log_record = {
            "timestamp": timestamp,
            "level": record.levelname,
            "ip": getattr(record, 'ip', '0.0.0.0'),
            "message": record.getMessage()
        }
        return json.dumps(log_record, cls=TacticalJSONEncoder)

class TacticalJSONFullFormatter(logging.Formatter):
    """
    Deep-dive JSON log formatter with full tactical intel (UA, Method, Path, User, Referrer).
    """
    def format(self, record):
        timestamp = datetime.datetime.fromtimestamp(record.created, datetime.timezone.utc).isoformat()
        
        # 1. Base Metadata
        log_record = {
            "timestamp": timestamp,
            "level": record.levelname,
            "ip": getattr(record, 'ip', '0.0.0.0'),
            "ua": getattr(record, 'ua', 'UNKNOWN_UA'),
            "method": getattr(record, 'method', 'UNKNOWN_METHOD'),
            "path": getattr(record, 'path', 'UNKNOWN_PATH'),
            "user": getattr(record, 'user', 'ANONYMOUS'),
            "referrer": getattr(record, 'referrer', 'NO_REFERRER'),
            "logger": record.name,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # 2. Append 'extra' metadata from the view
        standard_fields = [
            'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
            'funcName', 'levelname', 'levelno', 'lineno', 'module',
            'msecs', 'message', 'msg', 'name', 'pathname', 'process',
            'processName', 'relativeCreated', 'stack_info', 'thread', 'threadName',
            'ip', 'ua', 'method', 'path', 'user', 'referrer'
        ]
        
        for key, value in record.__dict__.items():
            if key not in standard_fields and key not in log_record:
                log_record[key] = value

        return json.dumps(log_record, cls=TacticalJSONEncoder)
