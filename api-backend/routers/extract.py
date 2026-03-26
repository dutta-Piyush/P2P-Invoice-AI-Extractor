import logging
from functools import lru_cache

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from core.config import settings
from core.exceptions import ExtractionError, UploadError
from core.file_validator import FileValidator
from core.limiter import limiter
from models.schemas import ExtractResponse
from services.extraction_service import (
    IExtractionService,
    LocalPdfStorage,
    OpenAIExtractionService,
)
from services.openai_extractor import OpenAIExtractor
from services.pdf_reader import PyMuPdfTextReader

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["extract"])


@lru_cache(maxsize=1)
def get_extraction_service() -> IExtractionService:
    storage = LocalPdfStorage(upload_dir="uploads")
    validator = FileValidator()
    return OpenAIExtractionService(
        storage=storage,
        validator=validator,
        reader=PyMuPdfTextReader(),
        extractor=OpenAIExtractor(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            ssl_verify=settings.ssl_verify,
            max_input_chars=settings.max_pdf_chars,
        ),
    )


@router.post("/extract", response_model=ExtractResponse)
@limiter.limit("10/minute")
async def extract(
    request: Request,
    file: UploadFile = File(...),
    extraction_service: IExtractionService = Depends(get_extraction_service),
) -> ExtractResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File is empty")

    try:
        result = await extraction_service.extract(
            filename=file.filename,
            content=content,
            content_type=file.content_type or "",
        )
        logger.info("Extraction successful for file: %s", file.filename)
        return result
    except UploadError as exc:
        logger.warning("Upload validation failed for %s: %s", file.filename, exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except ExtractionError as exc:
        logger.error("Extraction failed for %s: %s", file.filename, exc)
        raise HTTPException(status_code=422, detail=str(exc))

