import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.schemas import (
    CreateRequestPayload,
    OrderLine,
    RequestRecord,
    RequestStatus,
    StatusEvent,
)
from models.orm_models import RequestCounterORM, RequestORM, StatusEventORM

logger = logging.getLogger(__name__)

_UPLOAD_DIR = Path("uploads")

_TRANSITIONS: dict[str, frozenset[str]] = {
    "open":        frozenset({"in_progress", "cancelled", "rejected"}),
    "in_progress": frozenset({"closed", "cancelled", "rejected"}),
    "closed":      frozenset(),
    "cancelled":   frozenset(),
    "rejected":    frozenset(),
}


class IRequestService(ABC):
    @abstractmethod
    def create(self, payload: CreateRequestPayload, db: Session) -> RequestRecord: ...

    @abstractmethod
    def list_all(self, db: Session, skip: int = 0, limit: int = 50) -> list[RequestRecord]: ...

    @abstractmethod
    def get_by_id(self, request_id: str, db: Session) -> RequestRecord | None: ...

    @abstractmethod
    def update_status(self, request_id: str, new_status: RequestStatus, note: str, db: Session) -> RequestRecord | None: ...

    @abstractmethod
    def get_source_pdf_path(self, request_id: str, db: Session) -> str | None: ...


class RequestService(IRequestService):

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _event_to_schema(event: StatusEventORM) -> StatusEvent:
        return StatusEvent(
            from_status=event.from_status,
            to_status=event.to_status,
            at=event.at,
            note=event.note,
        )

    @staticmethod
    def _orm_to_schema(record: RequestORM) -> RequestRecord:
        return RequestRecord(
            id=record.id,
            requestor_name=record.requestor_name,
            title=record.title,
            vendor_name=record.vendor_name,
            vat_id=record.vat_id,
            department=record.department,
            commodity_group_id=record.commodity_group_id,
            order_lines=[OrderLine(**line) for line in record.order_lines],
            total_cost=record.total_cost,
            status=record.status,
            status_history=[RequestService._event_to_schema(e) for e in record.events],
            has_document=record.source_pdf is not None,
        )

    @staticmethod
    def _next_id(db: Session) -> str:
        counter = db.query(RequestCounterORM).filter(RequestCounterORM.id == 1).with_for_update().first()
        if counter is None:
            max_id: str | None = db.query(func.max(RequestORM.id)).scalar()
            seed = 0
            if max_id:
                try:
                    seed = int(max_id.split("-")[1])
                except (IndexError, ValueError):
                    pass
            counter = RequestCounterORM(id=1, last_value=seed)
            db.add(counter)
            db.flush()
        counter.last_value += 1
        db.flush()
        return f"REQ-{counter.last_value:03d}"

    def create(self, payload: CreateRequestPayload, db: Session) -> RequestRecord:
        new_id = self._next_id(db)
        source_pdf = str(_UPLOAD_DIR / payload.source_pdf) if payload.source_pdf else None
        orm = RequestORM(
            id=new_id,
            requestor_name=payload.requestor_name,
            title=payload.title,
            vendor_name=payload.vendor_name,
            vat_id=payload.vat_id,
            department=payload.department,
            commodity_group_id=payload.commodity_group_id,
            total_cost=payload.total_cost,
            status="open",
            source_pdf=source_pdf,
        )
        orm.order_lines = [line.model_dump() for line in payload.order_lines]

        initial_event = StatusEventORM(
            request_id=new_id,
            from_status=None,
            to_status="open",
            at=self._now(),
            note="Request created",
        )
        db.add(orm)
        db.flush()
        db.add(initial_event)

        db.refresh(orm)
        logger.info("Created request %s — '%s'", new_id, payload.title)
        return self._orm_to_schema(orm)

    def list_all(self, db: Session, skip: int = 0, limit: int = 50) -> list[RequestRecord]:
        records = (
            db.query(RequestORM)
            .order_by(RequestORM.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [self._orm_to_schema(r) for r in records]

    def get_by_id(self, request_id: str, db: Session) -> RequestRecord | None:
        orm = db.query(RequestORM).filter(RequestORM.id == request_id).first()
        if orm is None:
            return None
        return self._orm_to_schema(orm)

    def update_status(
        self,
        request_id: str,
        new_status: RequestStatus,
        note: str,
        db: Session,
    ) -> RequestRecord | None:
        orm = db.query(RequestORM).filter(RequestORM.id == request_id).first()
        if orm is None:
            return None

        allowed = _TRANSITIONS.get(orm.status, frozenset())
        if new_status != orm.status and new_status not in allowed:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot transition from '{orm.status}' to '{new_status}'",
            )

        clean_note = note.strip()
        if orm.status == new_status and not clean_note:
            logger.debug("Request %s — no change (same status, no note)", request_id)
            return self._orm_to_schema(orm)

        event = StatusEventORM(
            request_id=request_id,
            from_status=orm.status,
            to_status=new_status,
            at=self._now(),
            note=clean_note or "Updated by user",
        )
        orm.status = new_status
        db.add(event)
        db.flush()
        db.refresh(orm)

        logger.info(
            "Request %s: %s -> %s (note: %r)",
            request_id,
            event.from_status,
            new_status,
            clean_note,
        )
        return self._orm_to_schema(orm)

    def get_source_pdf_path(self, request_id: str, db: Session) -> str | None:
        orm = db.query(RequestORM).filter(RequestORM.id == request_id).first()
        if orm is None:
            return None
        return orm.source_pdf


_service = RequestService()


def get_request_service() -> RequestService:
    return _service
