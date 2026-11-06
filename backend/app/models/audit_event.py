"""AuditEvent model - chronological record of everything the agent did."""
import datetime
import uuid
from typing import Any
from sqlalchemy import String, DateTime, Text, ForeignKey, JSON, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id")
    )
    rider_id: Mapped[str] = mapped_column(String(20))

    # Event classification (matches SUBMISSION.md trace spec)
    event_type: Mapped[str] = mapped_column(String(30))
    # message_in, tool_call, decision, reply, error
    name: Mapped[str] = mapped_column(String(100))
    input_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    occurred_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Optional link to specific dispute
    dispute_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="audit_events")  # noqa: F821

    __table_args__ = (
        Index("ix_audit_events_conversation_id", "conversation_id"),
        Index("ix_audit_events_rider_id", "rider_id"),
        Index("ix_audit_events_occurred_at", "occurred_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditEvent {self.event_type}:{self.name} at {self.occurred_at}>"
