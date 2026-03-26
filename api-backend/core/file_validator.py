from abc import ABC, abstractmethod

from core.exceptions import FileTooLargeError, InvalidFileTypeError

_ALLOWED_MIME_TYPES: frozenset[str] = frozenset({"application/pdf"})
_PDF_MAGIC: bytes = b"%PDF"
_MAX_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB


class IFileValidator(ABC):
    @abstractmethod
    def validate(self, content_type: str, content: bytes) -> None:
        pass


class FileValidator(IFileValidator):
    def validate(self, content_type: str, content: bytes) -> None:
        self._check_mime_type(content_type)
        self._check_size(content)
        self._check_magic_bytes(content)

    def _check_mime_type(self, content_type: str) -> None:
        if content_type not in _ALLOWED_MIME_TYPES:
            raise InvalidFileTypeError(f"'{content_type}' is not allowed. Only PDF is accepted.")

    def _check_size(self, content: bytes) -> None:
        if len(content) > _MAX_SIZE_BYTES:
            raise FileTooLargeError(f"File exceeds {_MAX_SIZE_BYTES // (1024 * 1024)} MB limit.")

    def _check_magic_bytes(self, content: bytes) -> None:
        if not content.startswith(_PDF_MAGIC):
            raise InvalidFileTypeError("File content does not match a valid PDF signature.")
