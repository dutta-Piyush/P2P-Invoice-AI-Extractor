import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4

from core.file_validator import IFileValidator
from core.exceptions import AIServiceError, UploadError
from models.schemas import ExtractResponse
from services.pdf_reader import IPdfTextReader
from services.openai_extractor import OpenAIExtractor

logger = logging.getLogger(__name__)


class IPdfStorage(ABC):
	@abstractmethod
	def save_pdf(self, filename: str, content: bytes) -> str:
		pass

	@abstractmethod
	def delete_pdf(self, path: str) -> None:
		pass


class LocalPdfStorage(IPdfStorage):
	def __init__(self, upload_dir: str = "uploads") -> None:
		self._upload_dir = Path(upload_dir)

	def save_pdf(self, filename: str, content: bytes) -> str:
		try:
			self._ensure_directory()
			path = self._build_file_path(filename)
			self._write_file(path, content)
			return str(path)
		except PermissionError as exc:
			logger.error("Permission denied writing to upload directory '%s': %s", self._upload_dir, exc)
			raise UploadError("Server does not have permission to save the uploaded file.") from exc
		except OSError as exc:
			logger.error("Failed to save PDF to disk: %s", exc)
			raise UploadError("Failed to save the uploaded file. The server may be out of disk space.") from exc

	def _ensure_directory(self) -> None:
		self._upload_dir.mkdir(exist_ok=True)

	def _build_file_path(self, filename: str) -> Path:
		extension = Path(filename).suffix or ".pdf"
		return self._upload_dir / f"{uuid4().hex}{extension}"

	def _write_file(self, path: Path, content: bytes) -> None:
		path.write_bytes(content)
		logger.info("PDF saved: %s (%d bytes)", path.name, len(content))

	def delete_pdf(self, path: str) -> None:
		try:
			Path(path).unlink(missing_ok=True)
			logger.info("PDF deleted: %s", Path(path).name)
		except OSError as exc:
			logger.warning("Could not delete PDF %s: %s", path, exc)


class IExtractionService(ABC):
	@abstractmethod
	async def extract(self, filename: str, content: bytes, content_type: str) -> ExtractResponse:
		pass


class OpenAIExtractionService(IExtractionService):
	def __init__(
		self,
		storage: IPdfStorage,
		validator: IFileValidator,
		reader: IPdfTextReader,
		extractor: OpenAIExtractor,
	) -> None:
		self._storage = storage
		self._validator = validator
		self._reader = reader
		self._extractor = extractor

	@staticmethod
	def _empty_fallback(reason: str) -> ExtractResponse:
		return ExtractResponse(
			vendor_name="",
			vat_id="",
			department="",
			order_lines=[],
			total_cost=0.0,
			commodity_group_id="009",
			warnings=[reason],
		)

	async def extract(self, filename: str, content: bytes, content_type: str) -> ExtractResponse:
		logger.info("Starting OpenAI extraction for: %s", filename)
		self._validator.validate(content_type=content_type, content=content)
		saved_path = self._storage.save_pdf(filename=filename, content=content)
		try:
			pdf_text = self._reader.read_text(content)
			try:
				result = await asyncio.wait_for(
					asyncio.to_thread(self._extractor.extract, pdf_text),
					timeout=30.0,
				)
			except asyncio.TimeoutError:
				logger.warning("AI extraction timed out after 30s for: %s", filename)
				result = self._empty_fallback(
					"AI extraction timed out. Please fill in the fields manually."
				)
			except AIServiceError as exc:
				logger.warning("AI service failed for %s: %s", filename, exc)
				result = self._empty_fallback(str(exc))
		except Exception:
			# ExtractionError (scanned PDF) or UploadError — delete file and propagate
			self._storage.delete_pdf(saved_path)
			raise
		logger.info("Extraction completed for: %s — PDF retained at %s", filename, saved_path)
		result.source_pdf = Path(saved_path).name
		return result
