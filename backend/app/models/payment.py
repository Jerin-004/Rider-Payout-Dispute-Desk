"""Payment model - records of payment transactions made through PaySwift."""
import datetime
import uuid
from decimal import Decimal
from sqlalchemy import String, DateTime, Numeric, ForeignKey, Text, func, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dispute_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("disputes.id")
    )
    rider_id: Mapped[str] = mapped_column(String(20))

    # Amount in whole rupees (matching PaySwift requirement)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True, index=True)

    # PaySwift response
    payswift_payout_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payswift_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payswift_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payswift_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Our status
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    # PENDING, PROCESSING, COMPLETED, FAILED, UNCERTAIN

    initiated_by: Mapped[str] = mapped_column(String(50), default="auto")  # auto or operator_id
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    dispute: Mapped["Dispute"] = relationship("Dispute", back_populates="payments")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_payments_idempotency_key"),
        Index("ix_payments_dispute_id", "dispute_id"),
        Index("ix_payments_rider_id", "rider_id"),
        Index("ix_payments_rider_created", "rider_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Payment {self.id} rider={self.rider_id} amount={self.amount} status={self.status}>"
