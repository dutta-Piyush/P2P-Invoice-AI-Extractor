import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.limiter import limiter
from models.schemas import CreateRequestPayload, RequestRecord, UpdateStatusPayload
from services.request_service import RequestService, get_request_service
from models.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/requests", tags=["requests"])


@router.post("", response_model=RequestRecord, status_code=201)
@limiter.limit("20/minute")
def create_request(
    request: Request,
    payload: CreateRequestPayload, # Incoming request is validated and parsed.
    service: RequestService = Depends(get_request_service), # Returns the object of the singleton RequestService object.
    db: Session = Depends(get_db),
) -> RequestRecord:
    try:
        record = service.create(payload, db) # Creates a new procurement request.
    except SQLAlchemyError as exc:
        logger.exception("DB error creating request")
        raise HTTPException(status_code=500, detail="Failed to save request") from exc
    logger.info("POST /api/requests → created %s", record.id)
    return record


@router.get("", response_model=list[RequestRecord])
def list_requests(
    skip: int = 0,
    limit: int = 50,
    service: RequestService = Depends(get_request_service),
    db: Session = Depends(get_db),
) -> list[RequestRecord]:
    try:
        return service.list_all(db, skip=skip, limit=limit) # Retrieves a list of procurement requests.
    except SQLAlchemyError as exc:
        logger.exception("DB error listing requests")
        raise HTTPException(status_code=500, detail="Failed to retrieve requests") from exc


@router.patch("/{request_id}/status", response_model=RequestRecord)
@limiter.limit("30/minute")
def update_status(
    request: Request,
    request_id: str,
    payload: UpdateStatusPayload,
    service: RequestService = Depends(get_request_service),
    db: Session = Depends(get_db),
) -> RequestRecord:
    try:
        record = service.update_status(request_id, payload.status, payload.note, db) # Updates the status of a procurement request.
    except SQLAlchemyError as exc:
        logger.exception("DB error updating status for %s", request_id)
        raise HTTPException(status_code=500, detail="Failed to update status") from exc
    if record is None:
        raise HTTPException(status_code=404, detail=f"Request '{request_id}' not found")
    return record

# @router.get("/{request_id}", response_model=RequestRecord)
# def get_request(
#     request_id: int,
#     service: RequestService = Depends(get_request_service),
#     db: Session = Depends(get_db),
# ) -> RequestRecord:
#     try:
#         record = service.get_by_id(request_id, db) # Retrieves a procurement request by its ID.
#     except SQLAlchemyError as exc:
#         logger.exception("DB error fetching request %s", request_id)
#         raise HTTPException(status_code=500, detail="Failed to retrieve request") from exc
#     if record is None:
#         raise HTTPException(status_code=404, detail=f"Request '{request_id}' not found")
#     return record






# @router.get("/{request_id}/document")
# def download_document(
#     request_id: int,
#     service: RequestService = Depends(get_request_service),
#     db: Session = Depends(get_db),
# ) -> FileResponse:
#     try:
#         path = service.get_source_pdf_path(request_id, db) # Retrieves the path to the source PDF document.
#     except SQLAlchemyError as exc:
#         logger.exception("DB error fetching document path for %s", request_id)
#         raise HTTPException(status_code=500, detail="Failed to retrieve document") from exc
#     if path is None:
#         raise HTTPException(status_code=404, detail=f"Request '{request_id}' not found")
#     resolved = Path(path).resolve()
#     if not resolved.is_relative_to(Path("uploads").resolve()):
#         raise HTTPException(status_code=403, detail="Access denied")
#     if not resolved.is_file():
#         raise HTTPException(status_code=404, detail="Source document is not available")
#     return FileResponse(str(resolved), media_type="application/pdf", filename=f"{request_id}.pdf")
