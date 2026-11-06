"""Conversation model - tracks multi-turn rider conversations."""
import datetime
import uuid
from sqlalchemy import String, DateTime, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rider_id: Mapped[str] = mapped_column(String(20), ForeignKey("riders.rider_id"))
    state: Mapped[str] = mapped_column(String(30), default="NEW")
    # States: NEW, COLLECTING_INFORMATION, VERIFYING, WAITING_FOR_APPROVAL, PAYMENT_PROCESSING, RESOLVED, REJECTED, ESCALATED
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships — use explicit selectinload() in queries, not lazy loading
    rider: Mapped["Rider"] = relationship("Rider", back_populates="conversations")  # noqa: F821
    messages: Mapped[list["Message"]] = relationship(  # noqa: F821
        "Message", back_populates="conversation", order_by="Message.received_at", lazy="raise"
    )
    disputes: Mapped[list["Dispute"]] = relationship(  # noqa: F821
        "Dispute", back_populates="conversation", lazy="raise"
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(  # noqa: F821
        "AuditEvent", back_populates="conversation", order_by="AuditEvent.occurred_at", lazy="raise"
    )

    __table_args__ = (Index("ix_conversations_rider_id", "rider_id"),)

    def __repr__(self) -> str:
        return f"<Conversation {self.id} rider={self.rider_id} state={self.state}>"
