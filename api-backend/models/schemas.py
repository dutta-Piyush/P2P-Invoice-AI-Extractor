import re
from typing import Literal

from pydantic import BaseModel, field_validator



class OrderLine(BaseModel):
	position_description: str
	unit_price: float
	amount: float
	unit: str
	discount: float = 0.0  # percentage discount (0–100)
	total_price: float


class ExtractResponse(BaseModel):
	vendor_name: str
	vat_id: str
	department: str
	order_lines: list[OrderLine]
	total_cost: float
	commodity_group_id: str
	warnings: list[str] = []
	source_pdf: str | None = None  # server-side path retained for compliance


RequestStatus = Literal["open", "in_progress", "closed", "cancelled", "rejected"]


class StatusEvent(BaseModel):
	from_status: str | None
	to_status: str
	at: str
	note: str


_VALID_COMMODITY_IDS: frozenset[str] = frozenset(f"{i:03d}" for i in range(1, 51))


class CreateRequestPayload(BaseModel):
	requestor_name: str
	title: str
	vendor_name: str
	vat_id: str
	department: str
	commodity_group_id: str
	order_lines: list[OrderLine]
	total_cost: float
	source_pdf: str | None = None  # path set server-side after PDF extraction

	@field_validator("requestor_name", "title", "vendor_name", "department")
	@classmethod
	def must_not_be_blank(cls, v: str) -> str:
		if not v or not v.strip():
			raise ValueError("Field must not be blank")
		return v.strip()

	@field_validator("vat_id")
	@classmethod
	def validate_vat_id(cls, v: str) -> str:
		if not re.fullmatch(r"[A-Z]{2}\d{7,12}", v.strip()):
			raise ValueError("Invalid VAT ID format (e.g. DE123456789)")
		return v.strip()

	@field_validator("commodity_group_id")
	@classmethod
	def validate_commodity_group(cls, v: str) -> str:
		if v.strip() not in _VALID_COMMODITY_IDS:
			raise ValueError(f"Invalid commodity_group_id '{v}' — must be 001–050")
		return v.strip()

	@field_validator("source_pdf")
	@classmethod
	def validate_source_pdf(cls, v: str | None) -> str | None:
		if v is None:
			return None
		name = v.strip()
		if not name or "/" in name or "\\" in name or ".." in name:
			raise ValueError("Invalid source PDF reference")
		return name

	@field_validator("total_cost")
	@classmethod
	def validate_total_cost(cls, v: float) -> float:
		if v < 0:
			raise ValueError("total_cost must be non-negative")
		return v

	@field_validator("order_lines")
	@classmethod
	def validate_order_lines(cls, v: list[OrderLine]) -> list[OrderLine]:
		if not v:
			raise ValueError("At least one order line is required")
		return v


class RequestRecord(BaseModel):
	id: int
	requestor_name: str
	title: str
	vendor_name: str
	vat_id: str
	department: str
	commodity_group_id: str
	order_lines: list[OrderLine]
	total_cost: float
	status: RequestStatus
	status_history: list[StatusEvent]
	has_document: bool = False  # True when an original PDF is stored on disk


class UpdateStatusPayload(BaseModel):
	status: RequestStatus
	note: str = ""
