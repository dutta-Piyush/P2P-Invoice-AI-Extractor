class UploadError(Exception):
    """Base class for all upload-related business errors."""


class FileTooLargeError(UploadError):
    """Raised when file exceeds the allowed size limit."""


class InvalidFileTypeError(UploadError):
    """Raised when the file type is not permitted."""


class ExtractionError(Exception):
    """Raised when AI extraction fails or returns unparseable output."""


class AIServiceError(ExtractionError):
    """Raised when the OpenAI API is unreachable, rate-limited, or circuit-broken."""
