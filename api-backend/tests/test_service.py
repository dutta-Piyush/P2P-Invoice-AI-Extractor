"""Basic service-layer tests using an in-memory SQLite database."""
import pytest
from pydantic import ValidationError

from models.schemas import CreateRequestPayload, OrderLine
from services.request_service import RequestService

svc = RequestService()

_LINE = OrderLine(position_description="Widget", unit_price=10.0, amount=1.0, unit="pcs", total_price=10.0)

def _payload(**kw):
    defaults = dict(
        requestor_name="Alice", title="Supplies", vendor_name="Acme",
        vat_id="DE123456789", department="IT", commodity_group_id="015",
        order_lines=[_LINE], total_cost=10.0,
    )
    defaults.update(kw)
    return CreateRequestPayload(**defaults)


def test_create_assigns_sequential_id(db):
    r1 = svc.create(_payload(), db)
    r2 = svc.create(_payload(), db)
    assert r1.id == 1
    assert r2.id == 2

def test_create_initial_status_is_open(db):
    rec = svc.create(_payload(), db)
    assert rec.status == "open"

def test_get_by_id_returns_record(db):
    svc.create(_payload(), db)
    assert svc.get_by_id(1, db) is not None

def test_get_by_id_missing_returns_none(db):
    assert svc.get_by_id(999, db) is None

def test_update_status_changes_status(db):
    svc.create(_payload(), db)
    rec = svc.update_status(1, "in_progress", "Working on it", db)
    assert rec.status == "in_progress"
    rec = svc.update_status(1, "closed", "Done", db)
    assert rec.status == "closed"

def test_blank_title_rejected(db):
    with pytest.raises(ValidationError):
        _payload(title="  ")

def test_invalid_vat_id_rejected(db):
    with pytest.raises(ValidationError):
        _payload(vat_id="INVALID")


# ── source_pdf security tests ──────────────────────────────────────────────

def test_source_pdf_none_accepted():
    p = _payload(source_pdf=None)
    assert p.source_pdf is None

def test_source_pdf_bare_filename_accepted():
    p = _payload(source_pdf="abc123.pdf")
    assert p.source_pdf == "abc123.pdf"

def test_source_pdf_path_traversal_rejected():
    with pytest.raises(ValidationError):
        _payload(source_pdf="../../etc/passwd")

def test_source_pdf_forward_slash_rejected():
    with pytest.raises(ValidationError):
        _payload(source_pdf="uploads/abc.pdf")

def test_source_pdf_backslash_rejected():
    with pytest.raises(ValidationError):
        _payload(source_pdf="uploads\\abc.pdf")

def test_source_pdf_stored_with_uploads_prefix(db):
    rec = svc.create(_payload(source_pdf="abc123.pdf"), db)
    assert rec.has_document is True


# ── status transition tests ────────────────────────────────────────────────

def test_invalid_transition_open_to_closed_rejected(db):
    from fastapi import HTTPException
    svc.create(_payload(), db)
    with pytest.raises(HTTPException) as exc_info:
        svc.update_status(1, "closed", "", db)
    assert exc_info.value.status_code == 409

def test_valid_transition_open_to_in_progress(db):
    svc.create(_payload(), db)
    rec = svc.update_status(1, "in_progress", "Working", db)
    assert rec.status == "in_progress"

def test_valid_transition_open_to_cancelled(db):
    svc.create(_payload(), db)
    rec = svc.update_status(1, "cancelled", "Not needed", db)
    assert rec.status == "cancelled"

def test_closed_is_terminal(db):
    from fastapi import HTTPException
    svc.create(_payload(), db)
    svc.update_status(1, "in_progress", "WIP", db)
    svc.update_status(1, "closed", "Done", db)
    with pytest.raises(HTTPException) as exc_info:
        svc.update_status(1, "open", "Reopen", db)
    assert exc_info.value.status_code == 409
