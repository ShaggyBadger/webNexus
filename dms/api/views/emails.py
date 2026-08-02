import logging

from rest_framework import permissions, status
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from dms.api.mixins import StandardAPIResponseMixin
from dms.models import Document
from dms.services.document_email_service import DocumentEmailService

logger = logging.getLogger(__name__)


class DocumentEmailAnonThrottle(AnonRateThrottle):
    scope = "chart_email_anon"


class DocumentEmailUserThrottle(UserRateThrottle):
    scope = "chart_email_user"


class DocumentEmailAPIView(APIView, StandardAPIResponseMixin):
    """
    Commander's Intent:
    Lets operators send any accessible DMS document directly to email from the
    dashboard so field distribution does not depend on local downloads.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [DocumentEmailAnonThrottle, DocumentEmailUserThrottle]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.email_service = DocumentEmailService()

    def post(self, request, ulid: str):
        recipient_email = (request.data.get("email") or "").strip()
        if not recipient_email:
            if request.user.is_authenticated and request.user.email:
                recipient_email = request.user.email
            else:
                return self.error_response(
                    message="Email address is required.",
                    code="email_required",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        document = Document.objects.filter(id=ulid).select_related("category").first()
        if not document or document.status != "ACTIVE":
            return self.error_response(
                message="Document not found.",
                code="document_not_found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if not request.user.is_authenticated and not document.is_public:
            return self.error_response(
                message="Document not found.",
                code="document_not_found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        result = self.email_service.send_document(
            document=document,
            recipient_email=recipient_email,
        )
        if result.get("status") == "success":
            return self.success_response(data=result)

        return self.error_response(
            message=result.get("message", "Failed to send document email."),
            code=result.get("code", "document_email_delivery_failed"),
            details={"download_url": result.get("download_url", "")},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
