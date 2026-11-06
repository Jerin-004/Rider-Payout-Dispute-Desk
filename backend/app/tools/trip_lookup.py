"""Trip and payout-line lookup tools."""
import datetime
import logging
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trip import Trip
from app.models.payout_line import PayoutLine
from app.models.rider import Rider

log = logging.getLogger(__name__)


async def get_rider(db: AsyncSession, rider_id: str) -> Optional[Rider]:
    result = await db.execute(select(Rider).where(Rider.rider_id == rider_id))
    return result.scalar_one_or_none()


async def get_trip(db: AsyncSession, trip_id: str) -> Optional[Trip]:
    result = await db.execute(select(Trip).where(Trip.trip_id == trip_id))
    return result.scalar_one_or_none()


async def get_trips_for_rider_on_date(
    db: AsyncSession, rider_id: str, date: datetime.date
) -> list[Trip]:
    """All trips (any status) for a rider on a calendar day (IST = UTC+5:30)."""
    # Data is stored in UTC; IST day is UTC+5:30
    day_start_utc = datetime.datetime(date.year, date.month, date.day, 0, 0, 0) - datetime.timedelta(hours=5, minutes=30)
    day_end_utc = day_start_utc + datetime.timedelta(days=1)
    result = await db.execute(
        select(Trip).where(
            and_(
                Trip.rider_id == rider_id,
                Trip.started_at >= day_start_utc,
                Trip.started_at < day_end_utc,
            )
        )
    )
    return list(result.scalars().all())


async def get_payout_lines_for_trip(
    db: AsyncSession, trip_id: str
) -> list[PayoutLine]:
    result = await db.execute(
        select(PayoutLine).where(PayoutLine.trip_id == trip_id)
    )
    return list(result.scalars().all())


async def get_payout_lines_for_rider_on_date(
    db: AsyncSession, rider_id: str, date: datetime.date
) -> list[PayoutLine]:
    result = await db.execute(
        select(PayoutLine).where(
            and_(
                PayoutLine.rider_id == rider_id,
                PayoutLine.payout_date == date,
            )
        )
    )
    return list(result.scalars().all())


async def get_completed_trip_count_on_date(
    db: AsyncSession, rider_id: str, date: datetime.date
) -> int:
    """Count completed trips for incentive eligibility check."""
    trips = await get_trips_for_rider_on_date(db, rider_id, date)
    return sum(1 for t in trips if t.status == "completed")


async def total_paid_for_trip(db: AsyncSession, trip_id: str) -> Decimal:
    """Sum all payout lines for a trip."""
    lines = await get_payout_lines_for_trip(db, trip_id)
    return sum((line.amount for line in lines), Decimal("0"))


async def get_cancellation_penalties_for_rider_on_date(
    db: AsyncSession, rider_id: str, date: datetime.date
) -> list[PayoutLine]:
    result = await db.execute(
        select(PayoutLine).where(
            and_(
                PayoutLine.rider_id == rider_id,
                PayoutLine.payout_date == date,
                PayoutLine.line_type == "cancellation_penalty",
            )
        )
    )
    return list(result.scalars().all())
