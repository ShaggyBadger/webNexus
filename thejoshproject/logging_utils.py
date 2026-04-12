import logging
import threading
import json

# Thread-local storage to hold request-specific metadata
_thread_locals = threading.local()

def get_current_request_meta():
    """
    Retrieves the IP and User-Agent from the current thread's storage.
    """
    return {
        'ip': getattr(_thread_locals, 'ip', '0.0.0.0'),
        'ua': getattr(_thread_locals, 'ua', 'UNKNOWN_UA')
    }

class LoggingMiddleware:
    """
    Middleware to capture IP and User-Agent for every request.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Capture IP (Handling Nginx/Proxy with X-Forwarded-For)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')

        # 2. Capture User-Agent
        ua = request.META.get('HTTP_USER_AGENT', 'UNKNOWN_UA')

        # 3. Store in thread-local for the logger to find later
        _thread_locals.ip = ip
        _thread_locals.ua = ua

        response = self.get_response(request)
        return response

class TacticalFilter(logging.Filter):
    """
    Logging filter that injects 'ip' and 'ua' into every log record.
    """
    def filter(self, record):
        meta = get_current_request_meta()
        record.ip = meta['ip']
        record.ua = meta['ua']
        return True

class TacticalJSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    """
    def format(self, record):
        # 1. Define Standard Fields
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "ip": getattr(record, 'ip', '0.0.0.0'),
            "ua": getattr(record, 'ua', 'UNKNOWN_UA'),
            "logger": record.name,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # 2. Capture and append 'extra' fields
        standard_fields = [
            'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
            'funcName', 'levelname', 'levelno', 'lineno', 'module',
            'msecs', 'message', 'msg', 'name', 'pathname', 'process',
            'processName', 'relativeCreated', 'stack_info', 'thread', 'threadName'
        ]
        
        # Any field in record.__dict__ NOT in standard_fields is an 'extra' field
        for key, value in record.__dict__.items():
            if key not in standard_fields and key not in log_record:
                log_record[key] = value

        # 3. Return as single-line JSON
        return json.dumps(log_record)
