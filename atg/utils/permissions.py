from rest_framework import permissions
from django.conf import settings

class IsRemoteOCRClient(permissions.BasePermission):
    """
    TACTICAL SECURITY:
    Custom permission class that requires a high-entropy secret key
    to be passed in the 'X-ATG-Remote-Key' header.
    
    This isolates the high-privilege Remote OCR desktop client from 
    standard authenticated users.
    """
    def has_permission(self, request, view):
        remote_key = request.headers.get('X-ATG-Remote-Key')
        return remote_key == settings.ATG_REMOTE_OCR_KEY
