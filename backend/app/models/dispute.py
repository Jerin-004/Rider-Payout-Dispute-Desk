"""Dispute model - a single payout dispute for a specific trip/date/component."""
import datetime
import uuid
from decimal import Decimal
from sqlalchemy import String, DateTime, Numeric, ForeignKey, Text, Date, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Dispute(Base):
    __tablename__ = "disputes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rider_id: Mapped[str] = mapped_column(String(20))
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id")
    )

    # What the rider is disputing
    dispute_type: Mapped[str] = mapped_column(String(50))
    # Types: MISSING_PAYOUT, MISSING_SURGE, MISSING_INCENTIVE, INCORRECT_TRIP_AMOUNT,
    #        PAYMENT_NOT_RECEIVED, DUPLICATE_PENALTY, GENERAL_QUERY, UNKNOWN
    trip_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    delivery_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    claimed_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Calculated amounts
    expected_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    actual_paid: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    amount_owed: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(30), default="OPEN")
    # OPEN, VERIFYING, APPROVED, PAID, REJECTED, ESCALATED, NO_DISCREPANCY
    agent_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="disputes")  # noqa: F821
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="dispute", lazy="raise")  # noqa: F821
    approvals: Mapped[list["Approval"]] = relationship("Approval", back_populates="dispute", lazy="raise")  # noqa: F821

    __table_args__ = (
        Index("ix_disputes_rider_id", "rider_id"),
        Index("ix_disputes_conversation_id", "conversation_id"),
        Index("ix_disputes_trip_id", "trip_id"),
        Index("ix_disputes_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Dispute {self.id} rider={self.rider_id} type={self.dispute_type} status={self.status}>"
