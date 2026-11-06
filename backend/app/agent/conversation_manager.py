"""Conversation state management — load/save/transition conversation state."""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.rider import Rider

log = logging.getLogger(__name__)

# Valid state transitions
TRANSITIONS = {
    "NEW": {"COLLECTING_INFORMATION", "VERIFYING", "RESOLVED", "ESCALATED"},
    "COLLECTING_INFORMATION": {"COLLECTING_INFORMATION", "VERIFYING", "ESCALATED"},
    "VERIFYING": {"WAITING_FOR_APPROVAL", "PAYMENT_PROCESSING", "RESOLVED", "REJECTED", "ESCALATED"},
    "WAITING_FOR_APPROVAL": {"PAYMENT_PROCESSING", "REJECTED", "ESCALATED"},
    "PAYMENT_PROCESSING": {"RESOLVED", "ESCALATED"},
    "RESOLVED": {"COLLECTING_INFORMATION"},  # Rider can start new dispute
    "REJECTED": {"COLLECTING_INFORMATION"},
    "ESCALATED": {"COLLECTING_INFORMATION"},
}


async def get_or_create_conversation(
    db: AsyncSession, rider_id: str
) -> Conversation:
    """
    Get the most recent active conversation for the rider, or create a new one.
    'Active' means state is not RESOLVED/REJECTED after they already got a response.
    """
    result = await db.execute(
        select(Conversation)
        .where(Conversation.rider_id == rider_id)
        .options(
            selectinload(Conversation.messages),
            selectinload(Conversation.disputes),
            selectinload(Conversation.audit_events),
        )
        .order_by(Conversation.updated_at.desc())
        .limit(1)
    )
    conv = result.scalar_one_or_none()

    # If no conversation or last one is fully resolved/rejected, start fresh
    if conv is None or conv.state in ("RESOLVED", "REJECTED"):
        # But if it was resolved, we keep it and create a new one so history is preserved
        conv = Conversation(
            id=str(uuid.uuid4()),
            rider_id=rider_id,
            state="NEW",
        )
        db.add(conv)
        await db.flush()
        log.info("Created new conversation %s for rider %s", conv.id, rider_id)

    return conv


async def transition_conversation(
    conversation: Conversation, new_state: str, db: AsyncSession
) -> None:
    """Validate and apply state transition."""
    current = conversation.state
    allowed = TRANSITIONS.get(current, set())
    if new_state not in allowed:
        log.warning(
            "Invalid state transition %s → %s for conversation %s; ignoring",
            current, new_state, conversation.id,
        )
        return
    conversation.state = new_state
    conversation.updated_at = datetime.now(timezone.utc)
    await db.flush()


async def get_conversation_history(
    db: AsyncSession,
    conversation: Conversation,
) -> list[dict]:
    """Return conversation history as a list of role/text dicts — loads messages from DB."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.received_at.asc())
    )
    msgs = result.scalars().all()
    history = []
    for msg in msgs:
        history.append({"role": "rider", "text": msg.text})
        if msg.reply_text:
            history.append({"role": "agent", "text": msg.reply_text})
    return history


async def ensure_rider_exists(db: AsyncSession, rider_id: str) -> bool:
    """Return True if rider exists in DB."""
    result = await db.execute(select(Rider).where(Rider.rider_id == rider_id))
    return result.scalar_one_or_none() is not None
