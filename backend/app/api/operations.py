"""Operations endpoints — pending approvals, escalations, dashboard data, approval actions."""
import datetime
import logging
import uuid
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.approval import Approval
from app.models.dispute import Dispute
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.payment import Payment
from app.models.audit_event import AuditEvent
from app.schemas.operations import (
    PendingItem, ApprovalDecision, DisputeDetail,
    ConversationSummary, DashboardStats
)
from app.tools.payswift_client import get_payswift_client
from app.tools.policy_checker import evaluate_payment_eligibility, rupees_to_int
from app.core.exceptions import PaySwiftError

log = logging.getLogger(__name__)
router = APIRouter(prefix="/ops")


@router.get("/pending", response_model=list[PendingItem])
async def get_pending(db: AsyncSession = Depends(get_db)):
    """List all items waiting for ops: approvals and escalations."""
    result = await db.execute(
        select(Approval)
        .where(Approval.status == "PENDING")
        .order_by(Approval.created_at.asc())
    )
    approvals = result.scalars().all()

    items = []
    for a in approvals:
        # Get dispute info for context
        trip_id = None
        if a.dispute_id:
            dr = await db.execute(select(Dispute).where(Dispute.id == a.dispute_id))
            dispute = dr.scalar_one_or_none()
            if dispute:
                trip_id = dispute.trip_id

        items.append(PendingItem(
            id=a.id,
            rider_id=a.rider_id,
            type=a.approval_type,
            amount=float(a.amount) if a.amount is not None else None,
            reason=a.reason,
            created_at=a.created_at.isoformat(),
            dispute_id=a.dispute_id,
            trip_id=trip_id,
            agent_reasoning=a.agent_reasoning,
        ))

    return items


@router.post("/approvals/{approval_id}/approve")
async def approve_payment(
    approval_id: str,
    decision: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
):
    """
    Approve a pending payment.

    Safety:
    - Checks approval is PENDING before proceeding (prevents double-approval).
    - Re-verifies amount_owed from dispute record (never trusts approval.amount alone).
    - Uses rupees_to_int() to avoid truncation.
    - Checks for an existing COMPLETED payment with the same idempotency key before
      calling PaySwift, making the endpoint idempotent on retry.
    """
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"Approval is already {approval.status}")

    # Fetch the dispute for revalidation
    dr = await db.execute(select(Dispute).where(Dispute.id == approval.dispute_id))
    dispute = dr.scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    # Safe amount: min(approval.amount, dispute.amount_owed) — never exceed what is owed.
    # Use Decimal arithmetic, then rupees_to_int for PaySwift.
    approval_amount = Decimal(str(approval.amount)) if approval.amount else Decimal("0")
    dispute_owed = Decimal(str(dispute.amount_owed)) if dispute.amount_owed else Decimal("0")

    if approval_amount <= 0 or dispute_owed <= 0:
        raise HTTPException(status_code=422, detail="No positive amount to pay")

    safe_decimal = min(approval_amount, dispute_owed)
    safe_amount = rupees_to_int(safe_decimal)

    if safe_amount <= 0:
        raise HTTPException(status_code=422, detail="Amount rounds to zero after revalidation")

    idempotency_key = f"approval-{approval.id}"

    # --- IDEMPOTENCY: check if this approval already has a completed payment ---
    existing_payment = await db.scalar(
        select(Payment).where(Payment.idempotency_key == idempotency_key)
    )
    if existing_payment and existing_payment.status == "COMPLETED":
        log.info("Approval %s already has COMPLETED payment %s", approval_id, existing_payment.id)
        return {
            "status": "approved",
            "payout_id": existing_payment.payswift_payout_id,
            "amount": safe_amount,
            "note": "idempotent — payment was already completed",
        }

    # Fetch conversation for audit trail
    cr = await db.execute(select(Conversation).where(Conversation.id == dispute.conversation_id))
    conversation = cr.scalar_one_or_none()

    payswift = get_payswift_client()

    try:
        ps_result = await payswift.initiate_payout(
            rider_id=approval.rider_id,
            amount=safe_amount,
            reference=f"QuickDrop approved payout dispute={dispute.id}",
            idempotency_key=idempotency_key,
        )

        # Record payment
        payment = Payment(
            id=str(uuid.uuid4()),
            dispute_id=dispute.id,
            rider_id=approval.rider_id,
            amount=Decimal(str(safe_amount)),
            idempotency_key=idempotency_key,
            payswift_payout_id=ps_result.get("payout_id"),
            payswift_status=ps_result.get("status"),
            payswift_response=str(ps_result),
            status="COMPLETED",
            initiated_by=decision.operator_id,
        )
        db.add(payment)

        approval.status = "APPROVED"
        approval.operator_id = decision.operator_id
        approval.operator_comments = decision.comments
        approval.decided_at = datetime.datetime.now(datetime.timezone.utc)
        dispute.status = "PAID"

        if conversation:
            db.add(AuditEvent(
                id=str(uuid.uuid4()),
                conversation_id=conversation.id,
                rider_id=approval.rider_id,
                event_type="decision",
                name="ops_approval_payment",
                input_data={"operator": decision.operator_id, "amount": safe_amount},
                output_data={"payout_id": ps_result.get("payout_id"), "status": "COMPLETED"},
                dispute_id=dispute.id,
            ))

        await db.commit()
        return {
            "status": "approved",
            "payout_id": ps_result.get("payout_id"),
            "amount": safe_amount,
        }

    except PaySwiftError as exc:
        log.error("PaySwift failed on approval %s: %s", approval_id, exc)
        dispute.status = "ESCALATED"
        approval.agent_reasoning = (approval.agent_reasoning or "") + f"\nPaySwift failed: {exc}"
        await db.commit()
        raise HTTPException(status_code=502, detail=f"PaySwift payment failed: {exc}")


@router.post("/approvals/{approval_id}/reject")
async def reject_approval(
    approval_id: str,
    decision: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending approval."""
    result = await db.execute(select(Approval).where(Approval.id == approval_id))
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"Approval is already {approval.status}")

    dr = await db.execute(select(Dispute).where(Dispute.id == approval.dispute_id))
    dispute = dr.scalar_one_or_none()

    approval.status = "REJECTED"
    approval.operator_id = decision.operator_id
    approval.operator_comments = decision.comments
    approval.decided_at = datetime.datetime.now(datetime.timezone.utc)

    if dispute:
        dispute.status = "REJECTED"
        dispute.resolution_notes = f"Rejected by {decision.operator_id}: {decision.comments}"

    # Audit
    cr = await db.execute(select(Conversation).where(Conversation.id == (dispute.conversation_id if dispute else None)))
    conversation = cr.scalar_one_or_none()
    if conversation:
        evt = AuditEvent(
            id=str(uuid.uuid4()),
            conversation_id=conversation.id,
            rider_id=approval.rider_id,
            event_type="decision",
            name="ops_rejection",
            input_data={"operator": decision.operator_id, "comments": decision.comments},
            output_data={"status": "REJECTED"},
            dispute_id=dispute.id if dispute else None,
        )
        db.add(evt)

    await db.commit()
    return {"status": "rejected"}


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation)
        .order_by(desc(Conversation.updated_at))
        .limit(100)
        .options(selectinload(Conversation.messages), selectinload(Conversation.disputes))
    )
    conversations = result.scalars().all()

    summaries = []
    for conv in conversations:
        msgs = conv.messages
        latest_text = msgs[-1].text[:80] if msgs else None
        summaries.append(ConversationSummary(
            id=conv.id,
            rider_id=conv.rider_id,
            state=conv.state,
            message_count=len(msgs),
            dispute_count=len(conv.disputes),
            last_activity=conv.updated_at.isoformat(),
            latest_message=latest_text,
        ))

    return summaries


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(
            selectinload(Conversation.messages),
            selectinload(Conversation.disputes),
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {
        "id": conv.id,
        "rider_id": conv.rider_id,
        "state": conv.state,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
        "messages": [
            {
                "id": m.id,
                "text": m.text,
                "received_at": m.received_at.isoformat(),
                "reply": m.reply_text,
                "intent": m.intent,
            }
            for m in conv.messages
        ],
        "disputes": [
            {
                "id": d.id,
                "type": d.dispute_type,
                "trip_id": d.trip_id,
                "delivery_date": str(d.delivery_date) if d.delivery_date else None,
                "expected": float(d.expected_amount) if d.expected_amount else None,
                "actual_paid": float(d.actual_paid) if d.actual_paid else None,
                "amount_owed": float(d.amount_owed) if d.amount_owed else None,
                "status": d.status,
                "notes": d.agent_notes,
            }
            for d in conv.disputes
        ],
    }


@router.get("/disputes", response_model=list[DisputeDetail])
async def list_disputes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Dispute).order_by(desc(Dispute.created_at)).limit(200)
    )
    disputes = result.scalars().all()

    return [
        DisputeDetail(
            id=d.id,
            rider_id=d.rider_id,
            dispute_type=d.dispute_type,
            trip_id=d.trip_id,
            delivery_date=str(d.delivery_date) if d.delivery_date else None,
            expected_amount=float(d.expected_amount) if d.expected_amount else None,
            actual_paid=float(d.actual_paid) if d.actual_paid else None,
            amount_owed=float(d.amount_owed) if d.amount_owed else None,
            status=d.status,
            agent_notes=d.agent_notes,
            created_at=d.created_at.isoformat(),
        )
        for d in disputes
    ]


@router.get("/stats", response_model=DashboardStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate stats for the dashboard overview."""
    from sqlalchemy import case

    total = (await db.execute(select(func.count()).select_from(Dispute))).scalar_one()
    resolved = (await db.execute(
        select(func.count()).select_from(Dispute).where(Dispute.status.in_(["PAID", "NO_DISCREPANCY", "RESOLVED"]))
    )).scalar_one()
    pending_approvals = (await db.execute(
        select(func.count()).select_from(Approval).where(Approval.status == "PENDING")
    )).scalar_one()
    escalated = (await db.execute(
        select(func.count()).select_from(Dispute).where(Dispute.status == "ESCALATED")
    )).scalar_one()

    total_owed_row = await db.execute(
        select(func.coalesce(func.sum(Dispute.amount_owed), 0)).where(
            Dispute.amount_owed > 0
        )
    )
    total_owed = float(total_owed_row.scalar_one() or 0)

    total_paid_row = await db.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.status == "COMPLETED"
        )
    )
    total_paid = float(total_paid_row.scalar_one() or 0)

    return DashboardStats(
        total_disputes=total,
        resolved_disputes=resolved,
        pending_approvals=pending_approvals,
        escalated_disputes=escalated,
        total_amount_owed=total_owed,
        total_amount_paid=total_paid,
    )
