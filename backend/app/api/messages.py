"""POST /messages endpoint — main rider message handler."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.message import IncomingMessage, MessageReply
from app.agent.orchestrator import AgentOrchestrator
from app.core.exceptions import DuplicateMessageError

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/messages", response_model=MessageReply)
async def receive_message(
    payload: IncomingMessage,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive a rider message from the messaging vendor.
    Returns the reply text within ~10s.
    """
    log.info(
        "Message received: id=%s rider=%s text=%r",
        payload.message_id, payload.rider_id, payload.text[:80],
    )

    orchestrator = AgentOrchestrator(db)

    try:
        reply = await orchestrator.handle_message(
            message_id=payload.message_id,
            rider_id=payload.rider_id,
            text=payload.text,
            received_at=payload.received_at,
        )
    except DuplicateMessageError as e:
        # Duplicate delivery — return original reply without side effects
        log.info("Duplicate message %s — returning idempotent reply", payload.message_id)
        return MessageReply(reply=e.message)
    except Exception as e:
        log.exception("Unhandled error processing message %s: %s", payload.message_id, e)
        raise HTTPException(status_code=500, detail="Internal error processing message")

    return MessageReply(reply=reply)
