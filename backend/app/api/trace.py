"""GET /trace/{rider_id} — chronological agent audit trail."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.audit_event import AuditEvent
from app.models.conversation import Conversation
from app.schemas.message import TraceStep

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/trace/{rider_id}", response_model=list[TraceStep])
async def get_trace(rider_id: str, db: AsyncSession = Depends(get_db)):
    """
    Return chronological trace of everything the agent did for a rider.
    Each step has: at, type, name, input, output.
    """
    result = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.rider_id == rider_id)
        .order_by(AuditEvent.occurred_at.asc())
    )
    events = result.scalars().all()

    return [
        TraceStep(
            at=evt.occurred_at.isoformat(),
            type=evt.event_type,
            name=evt.name,
            input=evt.input_data,
            output=evt.output_data,
        )
        for evt in events
    ]
