import json
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.database import Base


# Tracks the last used request ID number for generating new IDs in the format "REQ-001", "REQ-002", etc.
class RequestCounterORM(Base):
    __tablename__ = "request_counter"

    id: Mapped[int] = mapped_column(primary_key=True)  # always a single row with id=1
    last_value: Mapped[int] = mapped_column(nullable=False, default=0)


# Represents a procurement request record in the database, including all relevant fields and relationships.
class RequestORM(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    requestor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    vendor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    vat_id: Mapped[str] = mapped_column(String(30), nullable=False)
    department: Mapped[str] = mapped_column(String(255), nullable=False)
    commodity_group_id: Mapped[str] = mapped_column(String(10), nullable=False)
    order_lines_json: Mapped[str] = mapped_column(Text, nullable=False)
    total_cost: Mapped[float] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    source_pdf: Mapped[str | None] = mapped_column(String(500), nullable=True)

    events: Mapped[list["StatusEventORM"]] = relationship(
        "StatusEventORM",
        back_populates="request",
        order_by="StatusEventORM.id",
        cascade="all, delete-orphan",
    )

    @property
    def order_lines(self) -> list[dict]:
        return json.loads(self.order_lines_json)

    @order_lines.setter
    def order_lines(self, value: list[dict]) -> None:
        self.order_lines_json = json.dumps(value)

# Represents a status change event for a procurement request, including the previous and new status, timestamp, and an optional note.
class StatusEventORM(Base):
    __tablename__ = "status_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    at: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")

    request: Mapped["RequestORM"] = relationship("RequestORM", back_populates="events")
