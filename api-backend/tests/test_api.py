"""Basic API-layer tests — service and DB are mocked via dependency_overrides."""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from main import app
from models.database import get_db
from models.schemas import OrderLine, RequestRecord, StatusEvent
from services.request_service import get_request_service

_RECORD = RequestRecord(
    id=1, requestor_name="Alice", title="Supplies", vendor_name="Acme",
    vat_id="DE123456789", department="IT", commodity_group_id="015",
    order_lines=[OrderLine(position_description="Widget", unit_price=10.0, amount=1.0, unit="pcs", total_price=10.0)],
    total_cost=10.0, status="open",
    status_history=[StatusEvent(from_status=None, to_status="open", at="2026-01-01 00:00", note="Created")],
)

_PAYLOAD = {
    "requestor_name": "Alice", "title": "Supplies", "vendor_name": "Acme",
    "vat_id": "DE123456789", "department": "IT", "commodity_group_id": "015",
    "order_lines": [{"position_description": "Widget", "unit_price": 10.0, "amount": 1.0, "unit": "pcs", "total_price": 10.0}],
    "total_cost": 10.0,
}

@pytest.fixture
def client():
    svc = MagicMock()
    svc.create.return_value = _RECORD
    svc.list_all.return_value = [_RECORD]
    svc.get_by_id.return_value = _RECORD
    svc.update_status.return_value = _RECORD.model_copy(update={"status": "closed"})

    app.dependency_overrides[get_request_service] = lambda: svc
    app.dependency_overrides[get_db] = lambda: (yield MagicMock())
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_create_request_returns_201(client):
    assert client.post("/api/v1/requests", json=_PAYLOAD).status_code == 201

def test_list_requests_returns_200(client):
    assert client.get("/api/v1/requests").status_code == 200


def test_get_request_returns_200(client):
    assert client.get("/api/v1/requests/1").status_code == 200


def test_get_missing_request_returns_404(client):
    app.dependency_overrides[get_request_service] = lambda: MagicMock(get_by_id=MagicMock(return_value=None))
    assert client.get("/api/v1/requests/999").status_code == 404


def test_update_status_returns_200(client):
    assert client.patch("/api/v1/requests/1/status", json={"status": "closed", "note": ""}).status_code == 200


def test_delete_endpoint_removed(client):
    assert client.delete("/api/v1/requests/1").status_code == 405


def test_cancelled_status_returns_200(client):
    app.dependency_overrides[get_request_service] = lambda: MagicMock(
        update_status=MagicMock(return_value=_RECORD.model_copy(update={"status": "cancelled"}))
    )
    assert client.patch("/api/v1/requests/1/status", json={"status": "cancelled", "note": "Duplicate of 1"}).status_code == 200


def test_rejected_status_returns_200(client):
    app.dependency_overrides[get_request_service] = lambda: MagicMock(
        update_status=MagicMock(return_value=_RECORD.model_copy(update={"status": "rejected"}))
    )
    assert client.patch("/api/v1/requests/1/status", json={"status": "rejected", "note": "Budget exceeded"}).status_code == 200

def test_db_error_returns_500(client):
    app.dependency_overrides[get_request_service] = lambda: MagicMock(create=MagicMock(side_effect=SQLAlchemyError()))
    assert client.post("/api/v1/requests", json=_PAYLOAD).status_code == 500


# ── source_pdf security tests ──────────────────────────────────────────────

def test_source_pdf_path_traversal_rejected(client):
    payload = {**_PAYLOAD, "source_pdf": "../../etc/passwd"}
    assert client.post("/api/v1/requests", json=payload).status_code == 422

def test_source_pdf_absolute_path_rejected(client):
    payload = {**_PAYLOAD, "source_pdf": "/etc/passwd"}
    assert client.post("/api/v1/requests", json=payload).status_code == 422

def test_source_pdf_backslash_path_rejected(client):
    payload = {**_PAYLOAD, "source_pdf": "uploads\\secret.pdf"}
    assert client.post("/api/v1/requests", json=payload).status_code == 422

def test_source_pdf_bare_filename_accepted(client):
    assert client.post("/api/v1/requests", json={**_PAYLOAD, "source_pdf": "abc123.pdf"}).status_code == 201


def test_download_outside_uploads_returns_403(client):
    svc = MagicMock(get_source_pdf_path=MagicMock(return_value="/etc/passwd"))
    app.dependency_overrides[get_request_service] = lambda: svc
    assert client.get("/api/v1/requests/1/document").status_code == 403
