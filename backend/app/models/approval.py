"""Approval model - human approval requests for payments exceeding auto-pay limit."""
import datetime
import uuid
from decimal import Decimal
from sqlalchemy import String, DateTime, Numeric, ForeignKey, Text, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dispute_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("disputes.id")
    )
    rider_id: Mapped[str] = mapped_column(String(20))

    # What needs approval
    approval_type: Mapped[str] = mapped_column(String(30), default="approval")
    # approval, escalation
    amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    agent_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Decision
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    # PENDING, APPROVED, REJECTED
    operator_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    operator_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    dispute: Mapped["Dispute"] = relationship("Dispute", back_populates="approvals")  # noqa: F821

    __table_args__ = (
        Index("ix_approvals_dispute_id", "dispute_id"),
        Index("ix_approvals_rider_id", "rider_id"),
        Index("ix_approvals_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Approval {self.id} dispute={self.dispute_id} status={self.status}>"
