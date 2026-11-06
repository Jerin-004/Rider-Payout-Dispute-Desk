"""Deterministic payout calculator following docs/policy.md exactly.

Policy:
- Base fare: ₹25
- Distance: ₹6/km after first 2km
- Surge multiplier applies to entire trip fare
- Round each trip to nearest rupee (0.5 rounds up)
- Daily incentive: ₹150 for 12+ completed trips in a day
- Cancellation penalty: ₹10 per rider-cancelled trip
- Customer cancellations: ₹0 (no penalty, no payment)
- "Day" = calendar day in IST
"""
import datetime
import logging
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.trip_lookup import (
    get_trip,
    get_trips_for_rider_on_date,
    get_payout_lines_for_trip,
    get_payout_lines_for_rider_on_date,
    get_cancellation_penalties_for_rider_on_date,
)
from app.models.trip import Trip

log = logging.getLogger(__name__)

BASE_FARE = Decimal("25")
PER_KM_RATE = Decimal("6")
FREE_KM = Decimal("2")
DAILY_INCENTIVE_TRIPS = 12
DAILY_INCENTIVE_AMOUNT = Decimal("150")
CANCELLATION_PENALTY = Decimal("10")


def calculate_trip_fare(distance_km: Decimal, surge_multiplier: Decimal) -> Decimal:
    """Calculate expected fare for a single completed trip."""
    extra_km = max(Decimal("0"), Decimal(str(distance_km)) - FREE_KM)
    raw_fare = BASE_FARE + PER_KM_RATE * extra_km
    surged = raw_fare * Decimal(str(surge_multiplier))
    # Round to nearest rupee, 0.5 rounds up
    return surged.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


async def calculate_expected_trip_payout(db: AsyncSession, trip_id: str) -> dict:
    """Calculate expected payout for a specific trip."""
    trip = await get_trip(db, trip_id)
    if trip is None:
        return {"error": "trip_not_found", "trip_id": trip_id}

    if trip.status == "cancelled_by_customer":
        return {
            "trip_id": trip_id,
            "status": trip.status,
            "expected": Decimal("0"),
            "note": "Customer cancellation earns nothing",
        }

    if trip.status == "cancelled_by_rider":
        return {
            "trip_id": trip_id,
            "status": trip.status,
            "expected": Decimal("0"),
            "note": "Rider cancellation incurs penalty (handled at day level)",
        }

    # completed trip
    fare = calculate_trip_fare(trip.distance_km, trip.surge_multiplier)
    lines = await get_payout_lines_for_trip(db, trip_id)
    actual_paid = sum((l.amount for l in lines), Decimal("0"))

    return {
        "trip_id": trip_id,
        "rider_id": trip.rider_id,
        "status": trip.status,
        "distance_km": float(trip.distance_km),
        "surge_multiplier": float(trip.surge_multiplier),
        "expected": float(fare),
        "actual_paid": float(actual_paid),
        "amount_owed": float(max(Decimal("0"), fare - actual_paid)),
        "payout_lines": [
            {"line_id": l.line_id, "type": l.line_type, "amount": float(l.amount)}
            for l in lines
        ],
    }


async def calculate_expected_day_payout(
    db: AsyncSession, rider_id: str, date: datetime.date
) -> dict:
    """Calculate expected payout for all trips on a given IST calendar day."""
    trips = await get_trips_for_rider_on_date(db, rider_id, date)
    payout_lines = await get_payout_lines_for_rider_on_date(db, rider_id, date)

    completed = [t for t in trips if t.status == "completed"]
    rider_cancelled = [t for t in trips if t.status == "cancelled_by_rider"]

    # Expected trip fares
    expected_trip_total = Decimal("0")
    trip_details = []
    for t in completed:
        fare = calculate_trip_fare(t.distance_km, t.surge_multiplier)
        expected_trip_total += fare
        trip_details.append({
            "trip_id": t.trip_id,
            "distance_km": float(t.distance_km),
            "surge": float(t.surge_multiplier),
            "expected_fare": float(fare),
        })

    # Expected incentive
    incentive_eligible = len(completed) >= DAILY_INCENTIVE_TRIPS
    expected_incentive = DAILY_INCENTIVE_AMOUNT if incentive_eligible else Decimal("0")

    # Expected penalties
    expected_penalty = CANCELLATION_PENALTY * len(rider_cancelled)

    expected_total = expected_trip_total + expected_incentive - expected_penalty

    # What was actually paid
    actual_trip_pay = sum(
        l.amount for l in payout_lines if l.line_type == "trip"
    )
    actual_incentive = sum(
        l.amount for l in payout_lines if l.line_type == "daily_incentive"
    )
    actual_penalties = sum(
        abs(l.amount) for l in payout_lines if l.line_type == "cancellation_penalty"
    )
    actual_total = actual_trip_pay + actual_incentive - actual_penalties

    return {
        "rider_id": rider_id,
        "date": str(date),
        "completed_trips": len(completed),
        "rider_cancelled_trips": len(rider_cancelled),
        "expected_trip_total": float(expected_trip_total),
        "expected_incentive": float(expected_incentive),
        "incentive_eligible": incentive_eligible,
        "expected_penalties": float(expected_penalty),
        "expected_total": float(expected_total),
        "actual_trip_pay": float(actual_trip_pay),
        "actual_incentive": float(actual_incentive),
        "actual_penalties_applied": float(actual_penalties),
        "actual_total": float(actual_total),
        "amount_owed": float(max(Decimal("0"), expected_total - actual_total)),
        "trip_details": trip_details,
    }


async def check_incentive_eligibility(
    db: AsyncSession, rider_id: str, date: datetime.date
) -> dict:
    """Check if rider qualifies for daily incentive on a given date."""
    trips = await get_trips_for_rider_on_date(db, rider_id, date)
    completed = [t for t in trips if t.status == "completed"]
    eligible = len(completed) >= DAILY_INCENTIVE_TRIPS
    payout_lines = await get_payout_lines_for_rider_on_date(db, rider_id, date)
    incentive_paid = any(l.line_type == "daily_incentive" for l in payout_lines)

    return {
        "rider_id": rider_id,
        "date": str(date),
        "completed_trips": len(completed),
        "required_trips": DAILY_INCENTIVE_TRIPS,
        "eligible": eligible,
        "incentive_paid": incentive_paid,
        "amount_owed": float(DAILY_INCENTIVE_AMOUNT) if (eligible and not incentive_paid) else 0.0,
    }
