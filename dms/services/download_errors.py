class DocumentDownloadErrorMixin:
    """Attach a stable diagnostic code and safe document context to failures."""

    def __init__(
        self,
        message: str,
        *,
        reason_code: str,
        document=None,
        document_id: str | None = None,
    ) -> None:
        self.reason_code = reason_code
        self.document = document
        self.document_id = str(document.id) if document is not None else document_id
        super().__init__(message)


class DocumentDownloadValueError(DocumentDownloadErrorMixin, ValueError):
    """Expected missing, inactive, or unsafe document download failure."""


class DocumentDownloadPermissionError(DocumentDownloadErrorMixin, PermissionError):
    """Expected access-denied document download failure."""


class DocumentDownloadFileNotFoundError(DocumentDownloadErrorMixin, FileNotFoundError):
    """Expected missing file in document storage."""
