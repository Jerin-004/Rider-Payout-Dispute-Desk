"""Unit tests for the deterministic payout calculator.
These do NOT require a database connection.
"""
from decimal import Decimal
import pytest

from app.tools.payout_calculator import calculate_trip_fare, BASE_FARE, PER_KM_RATE


def test_base_fare_only():
    """Trip under 2km: base fare only."""
    fare = calculate_trip_fare(Decimal("1.5"), Decimal("1.0"))
    assert fare == Decimal("25")


def test_exactly_2km():
    """Exactly 2km: no extra distance charge."""
    fare = calculate_trip_fare(Decimal("2.0"), Decimal("1.0"))
    assert fare == Decimal("25")


def test_extra_distance():
    """7.4km: 25 + 6*5.4 = 25+32.4 = 57.4 → 57."""
    fare = calculate_trip_fare(Decimal("7.4"), Decimal("1.0"))
    assert fare == Decimal("57")


def test_surge_multiplier():
    """6km with 1.5x surge: (25+6*4)*1.5 = 49*1.5 = 73.5 → 74."""
    fare = calculate_trip_fare(Decimal("6.0"), Decimal("1.5"))
    assert fare == Decimal("74")


def test_rounding_half_up():
    """5.0km with 1.5x surge: (25+18)*1.5 = 64.5 → 65."""
    fare = calculate_trip_fare(Decimal("5.0"), Decimal("1.5"))
    assert fare == Decimal("65")


def test_known_scenario_r026_t672899():
    """R026 / T672899: 7.4km, 1.0x → expected ₹57, paid ₹25, owed ₹32."""
    fare = calculate_trip_fare(Decimal("7.4"), Decimal("1.0"))
    paid = Decimal("25")
    assert fare == Decimal("57")
    assert fare - paid == Decimal("32")


def test_known_scenario_r003_t926334():
    """R003 / T926334: 6.0km, 1.5x → expected ₹74, paid ₹49, owed ₹25."""
    fare = calculate_trip_fare(Decimal("6.0"), Decimal("1.5"))
    paid = Decimal("49")
    assert fare == Decimal("74")
    assert fare - paid == Decimal("25")


def test_known_scenario_r007_t840677():
    """R007 / T840677: 9.0km, 1.5x → (25+42)*1.5 = 101, paid ₹67, owed ₹34."""
    fare = calculate_trip_fare(Decimal("9.0"), Decimal("1.5"))
    paid = Decimal("67")
    assert fare == Decimal("101")
    assert fare - paid == Decimal("34")


def test_known_scenario_r033_t795007_t206956():
    """R033: T795007 (12km) + T206956 (13km), no surge, both unpaid → ₹85+₹91=₹176."""
    f1 = calculate_trip_fare(Decimal("12.0"), Decimal("1.0"))
    f2 = calculate_trip_fare(Decimal("13.0"), Decimal("1.0"))
    assert f1 == Decimal("85")
    assert f2 == Decimal("91")
    assert f1 + f2 == Decimal("176")


def test_policy_auto_pay_limit():
    """Auto-pay limit is ₹200."""
    from app.config import get_settings
    settings = get_settings()
    assert settings.auto_pay_limit_rupees == 200


def test_policy_dispute_window():
    """Dispute window is 7 days."""
    from app.tools.policy_checker import is_within_dispute_window
    import datetime
    today = datetime.date(2026, 9, 22)
    assert is_within_dispute_window(datetime.date(2026, 9, 22), today) is True
    assert is_within_dispute_window(datetime.date(2026, 9, 15), today) is True
    assert is_within_dispute_window(datetime.date(2026, 9, 14), today) is False


def test_t312538_distance_correction():
    """T312538 distance 5000 in CSV should be treated as 5.0km."""
    # After correction in seeder: 5000/1000 = 5.0
    fare = calculate_trip_fare(Decimal("5.0"), Decimal("1.5"))
    paid = Decimal("43")
    # Expected: 65 - 43 = 22 (matches conversations.json payout=22)
    assert fare == Decimal("65")
    assert fare - paid == Decimal("22")
