"""Message model - individual messages from riders via the messaging vendor."""
import datetime
import uuid
from typing import Any
from sqlalchemy import String, DateTime, Text, ForeignKey, JSON, func, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Vendor-assigned message ID - unique to prevent duplicate processing
    message_id: Mapped[str] = mapped_column(String(200), unique=True)
    rider_id: Mapped[str] = mapped_column(String(20))
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id")
    )
    text: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reply_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Extracted agent analysis stored as JSON
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extracted_entities: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    agent_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("message_id", name="uq_messages_message_id"),
        Index("ix_messages_rider_id", "rider_id"),
        Index("ix_messages_conversation_id", "conversation_id"),
    )

    def __repr__(self) -> str:
        return f"<Message {self.message_id} rider={self.rider_id}>"
