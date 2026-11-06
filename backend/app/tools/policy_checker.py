"""Deterministic policy enforcement.

All financial policy decisions happen here, NEVER in the LLM.

Rules from docs/policy.md and BRIEF.md:
1. Auto-pay: up to ₹200 per dispute, once per rider per day.
2. Larger or repeat payouts → human approval required.
3. Never pay more than amount actually owed.
4. Reconcile against PaySwift, not local DB.
5. Only accept disputes within last 7 days.
"""
import datetime
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.payment import Payment

log = logging.getLogger(__name__)

settings = get_settings()

AUTO_PAY_LIMIT = Decimal(str(settings.auto_pay_limit_rupees))
DISPUTE_WINDOW_DAYS = settings.dispute_window_days


def is_within_dispute_window(date: datetime.date, reference_date: datetime.date | None = None) -> bool:
    """Check if a delivery date is within the 7-day dispute window."""
    today = reference_date or datetime.date.today()
    age = (today - date).days
    return 0 <= age <= DISPUTE_WINDOW_DAYS


def rupees_to_int(amount: Decimal) -> int:
    """
    Convert a Decimal rupee amount to an integer, rounding half-up.
    PaySwift requires integer amounts. Never truncate silently.
    """
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


async def has_auto_payment_today(
    db: AsyncSession, rider_id: str, ist_date: datetime.date | None = None
) -> bool:
    """
    Return True if rider already received an automatic payout on the given IST date.

    Fix: compare against the IST calendar date explicitly, not against func.current_date()
    which returns the UTC date and can disagree with IST wall clock around midnight.
    """
    if ist_date is None:
        ist_date = datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        ).date()

    # Pass the IST date as a parameter — DB stores created_at in UTC, so we convert
    # to IST inside SQL to stay consistent regardless of DB timezone setting.
    #
    # PostgreSQL: DATE(created_at AT TIME ZONE 'Asia/Kolkata')
    # SQLite (tests): DATE(DATETIME(created_at, '+5 hours', '30 minutes'))
    # We use a parameterised date comparison that works on both by fetching
    # records for the rider and filtering in Python (avoids dialect differences
    # in test vs production while still being safe).

    # Fetch today's auto-completed payments for this rider
    # created_at is UTC; IST = UTC+5:30
    ist_offset = datetime.timedelta(hours=5, minutes=30)
    day_start_utc = datetime.datetime(
        ist_date.year, ist_date.month, ist_date.day, 0, 0, 0,
        tzinfo=datetime.timezone.utc
    ) - ist_offset  # IST midnight in UTC

    day_end_utc = day_start_utc + datetime.timedelta(days=1)

    result = await db.execute(
        select(func.count()).where(
            and_(
                Payment.rider_id == rider_id,
                Payment.initiated_by == "auto",
                Payment.status == "COMPLETED",
                Payment.created_at >= day_start_utc,
                Payment.created_at < day_end_utc,
            )
        )
    )
    count = result.scalar_one()
    return count > 0


class PolicyDecision:
    def __init__(
        self,
        can_auto_pay: bool,
        requires_approval: bool,
        reason: str,
        safe_amount: Decimal,
    ):
        self.can_auto_pay = can_auto_pay
        self.requires_approval = requires_approval
        self.reason = reason
        # safe_amount is always the exact Decimal, never truncated.
        # Callers must use rupees_to_int(safe_amount) when sending to PaySwift.
        self.safe_amount = safe_amount

    def __repr__(self) -> str:
        return (
            f"PolicyDecision(auto={self.can_auto_pay}, approval={self.requires_approval}, "
            f"amount={self.safe_amount}, reason={self.reason!r})"
        )


async def evaluate_payment_eligibility(
    db: AsyncSession,
    rider_id: str,
    amount_owed: Decimal,
    dispute_date: datetime.date | None = None,
    reference_date: datetime.date | None = None,
) -> PolicyDecision:
    """
    Evaluate whether an automatic payment can be made or requires approval.

    All amounts stay as Decimal throughout. Callers convert to int only at the
    PaySwift call boundary using rupees_to_int().
    """
    amount_owed = Decimal(str(amount_owed))

    # No money owed → nothing to do
    if amount_owed <= Decimal("0"):
        return PolicyDecision(
            can_auto_pay=False,
            requires_approval=False,
            reason="No discrepancy found. No payment required.",
            safe_amount=Decimal("0"),
        )

    # Check dispute window
    if dispute_date and not is_within_dispute_window(dispute_date, reference_date):
        return PolicyDecision(
            can_auto_pay=False,
            requires_approval=False,
            reason=f"Dispute date {dispute_date} is outside the 7-day window.",
            safe_amount=Decimal("0"),
        )

    # Check already had auto-pay today (IST)
    ist_today = reference_date  # reference_date is already IST date from orchestrator
    already_paid_today = await has_auto_payment_today(db, rider_id, ist_today)

    if already_paid_today:
        return PolicyDecision(
            can_auto_pay=False,
            requires_approval=True,
            reason="Rider already received an automatic payout today. Requires ops approval.",
            safe_amount=amount_owed,
        )

    # Check amount limit
    if amount_owed > AUTO_PAY_LIMIT:
        return PolicyDecision(
            can_auto_pay=False,
            requires_approval=True,
            reason=(
                f"Amount ₹{amount_owed} exceeds auto-pay limit of ₹{AUTO_PAY_LIMIT}. "
                "Requires ops approval."
            ),
            safe_amount=amount_owed,
        )

    # All checks passed — eligible for automatic payment
    return PolicyDecision(
        can_auto_pay=True,
        requires_approval=False,
        reason=f"Eligible for automatic payment of ₹{amount_owed}.",
        safe_amount=amount_owed,
    )


def validate_trip_id(raw: str) -> str | None:
    """
    Validate and sanitise a trip ID extracted by the LLM.

    Production format: T followed by 4-8 digits (e.g. T926334, T9264).
    Test format:       T followed by 4-8 alphanumeric chars (e.g. TTEST1).
    Rejects anything with SQL metacharacters, spaces, or unexpected length.
    """
    import re
    if not isinstance(raw, str):
        return None
    stripped = raw.strip().upper()
    if re.fullmatch(r"T[A-Z0-9]{4,8}", stripped):
        return stripped
    return None


def validate_claimed_amount(raw) -> Decimal | None:
    """
    Convert LLM-extracted claimed_amount to a Decimal.
    Returns None if invalid, negative, or suspiciously large (>10000).
    The claimed amount is NEVER used for payment; it is stored for reference only.
    """
    if raw is None:
        return None
    try:
        val = Decimal(str(raw))
        if val < Decimal("0") or val > Decimal("10000"):
            return None
        return val
    except Exception:
        return None
