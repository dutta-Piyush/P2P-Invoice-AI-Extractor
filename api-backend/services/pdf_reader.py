import logging
import fitz  # PyMuPDF

from core.exceptions import ExtractionError

logger = logging.getLogger(__name__)

_MIN_TEXT_LENGTH = 50  # characters — below this we assume a scanned/image PDF

class PyMuPdfTextReader():
    def read_text(self, content: bytes) -> str:
        with fitz.open(stream=content, filetype="pdf") as doc:
            text = self._extract_pages(doc)
            logger.debug("Extracted %d pages, %d characters", len(doc), len(text))
        if len(text.strip()) < _MIN_TEXT_LENGTH:
            raise ExtractionError(
                "This PDF appears to be a scanned image and contains no extractable text. "
                "Automatic extraction is not supported for this file — please fill in the fields manually."
            )
        return text

    def _extract_pages(self, doc: fitz.Document) -> str:
        return "\n".join(page.get_text() for page in doc).strip()
