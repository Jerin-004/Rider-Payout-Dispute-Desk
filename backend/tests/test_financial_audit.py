"""
Financial audit tests.
Every test creates its own AsyncClient to avoid fixture connection-leak hangs.
"""
import datetime
import os
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

os.environ["LLM_PROVIDER"] = "mock"
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ.setdefault("PAYSWIFT_BASE_URL", "http://localhost:8081")

from tests.conftest import MockPaySwift, TimeoutPaySwift, TimeoutThenFoundPaySwift  # noqa: E402


def _m(rider_id, text, mid=None, ts="2026-09-22T09:00:00+05:30"):
    return {
        "message_id": mid or f"fa.{uuid.uuid4().hex[:8]}",
        "rider_id": rider_id, "text": text, "received_at": ts,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Pure unit tests (no DB, no app)
# ──────────────────────────────────────────────────────────────────────────────

class TestRupeesRounding:
    def test_round_half_up(self):
        from app.tools.policy_checker import rupees_to_int
        assert rupees_to_int(Decimal("24.5")) == 25
        assert rupees_to_int(Decimal("24.4")) == 24
        assert rupees_to_int(Decimal("24.9")) == 25
        assert rupees_to_int(Decimal("74.9")) == 75   # int() would give 74 — wrong
        assert rupees_to_int(Decimal("200.0")) == 200


class TestInputSanitisation:
    def _san(self, raw):
        from app.agent.orchestrator import AgentOrchestrator
        o = object.__new__(AgentOrchestrator)
        return o._sanitise_intent_output(raw)

    def test_valid_intent(self):
        out = self._san({"intent": "MISSING_SURGE", "trip_ids": ["T926334"],
                          "delivery_date": "2026-09-20"})
        assert out["intent"] == "MISSING_SURGE"
        assert out["trip_ids"] == ["T926334"]
        assert out["delivery_date"] == datetime.date(2026, 9, 20)

    def test_unknown_intent_normalised(self):
        assert self._san({"intent": "HACK_THE_PLANET"})["intent"] == "UNKNOWN"

    def test_sql_injection_trip_id_discarded(self):
        out = self._san({"intent": "MISSING_PAYOUT",
                          "trip_ids": ["T12345; DROP TABLE trips", "T99",
                                       "T123456789012", "T926334"]})
        assert out["trip_ids"] == ["T926334"]

    def test_trip_ids_capped(self):
        ids = [f"T{100000 + i}" for i in range(20)]
        out = self._san({"intent": "MULTIPLE_DISPUTES", "trip_ids": ids})
        assert len(out["trip_ids"]) <= 10

    def test_date_outside_2026_discarded(self):
        assert self._san({"delivery_date": "2025-01-01"})["delivery_date"] is None

    def test_invalid_date_discarded(self):
        assert self._san({"delivery_date": "not-a-date"})["delivery_date"] is None

    def test_numeric_string_not_valid_trip_id(self):
        assert self._san({"trip_ids": ["300", "500"]})["trip_ids"] == []

    def test_non_list_trip_ids_discarded(self):
        assert self._san({"trip_ids": "T926334"})["trip_ids"] == []

    def test_claimed_amount_validated(self):
        from app.tools.policy_checker import validate_claimed_amount
        assert validate_claimed_amount("300") == Decimal("300")
        assert validate_claimed_amount("-50") is None
        assert validate_claimed_amount("99999") is None
        assert validate_claimed_amount("bad") is None
        assert validate_claimed_amount(None) is None

    def test_unknown_missing_info_discarded(self):
        out = self._san({"missing_information": ["trip_id", "HACK", "delivery_date"]})
        assert "HACK" not in out["missing_information"]
        assert "trip_id" in out["missing_information"]

    def test_bad_language_defaults_to_hinglish(self):
        assert self._san({"rider_message_language": "klingon"})["rider_message_language"] == "hinglish"


class TestAmountCalculations:
    def test_positive_owed(self):
        from app.tools.payout_calculator import calculate_trip_fare
        fare = calculate_trip_fare(Decimal("6.0"), Decimal("1.5"))   # 74
        assert max(Decimal("0"), fare - Decimal("49")) == Decimal("25")

    def test_zero_owed_when_overpaid(self):
        from app.tools.payout_calculator import calculate_trip_fare
        fare = calculate_trip_fare(Decimal("6.0"), Decimal("1.5"))   # 74
        assert max(Decimal("0"), fare - Decimal("100")) == Decimal("0")

    def test_claimed_amount_never_becomes_payment(self):
        from app.tools.payout_calculator import calculate_trip_fare
        fare = calculate_trip_fare(Decimal("6.0"), Decimal("1.5"))
        owed = max(Decimal("0"), fare - Decimal("49"))   # 25
        assert owed == Decimal("25")
        assert owed != Decimal("999")


class TestPolicyChecker:
    def test_auto_pay_limit_200(self):
        from app.config import get_settings
        assert get_settings().auto_pay_limit_rupees == 200

    def test_dispute_window_7_days(self):
        from app.tools.policy_checker import is_within_dispute_window
        today = datetime.date(2026, 9, 22)
        assert is_within_dispute_window(datetime.date(2026, 9, 22), today)
        assert is_within_dispute_window(datetime.date(2026, 9, 15), today)
        assert not is_within_dispute_window(datetime.date(2026, 9, 14), today)
        assert not is_within_dispute_window(datetime.date(2026, 9, 23), today)

    def test_ist_utc_midnight_boundary(self):
        ist_offset = datetime.timedelta(hours=5, minutes=30)
        day_start_utc = (
            datetime.datetime(2026, 9, 22, 0, 0, tzinfo=datetime.timezone.utc) - ist_offset
        )
        # IST 22 Sep 00:00 = UTC 21 Sep 18:30
        assert day_start_utc == datetime.datetime(2026, 9, 21, 18, 30, tzinfo=datetime.timezone.utc)
        day_end_utc = day_start_utc + datetime.timedelta(days=1)
        late = datetime.datetime(2026, 9, 22, 18, 29, tzinfo=datetime.timezone.utc)
        assert day_start_utc <= late < day_end_utc
        outside = datetime.datetime(2026, 9, 22, 18, 31, tzinfo=datetime.timezone.utc)
        assert not (day_start_utc <= outside < day_end_utc)

    @pytest.mark.asyncio
    async def test_zero_amount_no_payment(self):
        from app.tools.policy_checker import evaluate_payment_eligibility
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one=lambda: 0))
        d = await evaluate_payment_eligibility(mock_db, "R1", Decimal("0"))
        assert not d.can_auto_pay and not d.requires_approval

    @pytest.mark.asyncio
    async def test_above_200_requires_approval(self):
        from app.tools.policy_checker import evaluate_payment_eligibility
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one=lambda: 0))
        d = await evaluate_payment_eligibility(
            mock_db, "R1", Decimal("201"),
            dispute_date=datetime.date(2026, 9, 20),
            reference_date=datetime.date(2026, 9, 22),
        )
        assert not d.can_auto_pay and d.requires_approval

    @pytest.mark.asyncio
    async def test_second_same_day_requires_approval(self):
        from app.tools.policy_checker import evaluate_payment_eligibility
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one=lambda: 1))
        d = await evaluate_payment_eligibility(
            mock_db, "R1", Decimal("25"),
            dispute_date=datetime.date(2026, 9, 20),
            reference_date=datetime.date(2026, 9, 22),
        )
        assert not d.can_auto_pay and d.requires_approval
        assert "already received" in d.reason


class TestPaySwiftUncertainError:
    def test_is_a_payswift_error(self):
        from app.core.exceptions import PaySwiftError, PaySwiftUncertainError
        e = PaySwiftUncertainError("t", idempotency_key="k")
        assert isinstance(e, PaySwiftError)

    def test_carries_key(self):
        from app.core.exceptions import PaySwiftUncertainError
        e = PaySwiftUncertainError("t", idempotency_key="idem-abc")
        assert e.idempotency_key == "idem-abc"

    @pytest.mark.asyncio
    async def test_client_raises_on_timeout(self):
        import httpx
        from app.tools.payswift_client import PaySwiftClient
        from app.core.exceptions import PaySwiftUncertainError
        client = PaySwiftClient(base_url="http://localhost:9999")
        with patch.object(client, "_client") as ctx:
            mc = AsyncMock()
            ctx.return_value.__aenter__ = AsyncMock(return_value=mc)
            ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            mc.post = AsyncMock(side_effect=httpx.TimeoutException("t"))
            with pytest.raises(PaySwiftUncertainError) as ei:
                await client.initiate_payout("R1", 25, "ref", idempotency_key="k1")
            assert ei.value.idempotency_key == "k1"

    @pytest.mark.asyncio
    async def test_empty_key_raises(self):
        from app.tools.payswift_client import PaySwiftClient
        client = PaySwiftClient(base_url="http://localhost:9999")
        with pytest.raises((ValueError, TypeError)):
            await client.initiate_payout("R1", 25, "ref", idempotency_key="")


# ──────────────────────────────────────────────────────────────────────────────
# Integration tests — each gets its own DB via appdb fixture
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_duplicate_message_no_double_payment(appdb):
    """Same message_id sent twice → idempotent reply, exactly one DB row."""
    app, Session, _ps = appdb
    mid = f"dup.{uuid.uuid4().hex[:6]}"
    payload = _m("RTEST", "TTEST1 ka surge nahi mila", mid=mid)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.post("/messages", json=payload)
        r2 = await c.post("/messages", json=payload)
    assert r1.status_code == 200 and r2.status_code == 200
    from app.models.message import Message
    from sqlalchemy import select
    async with Session() as s:
        rows = (await s.execute(select(Message).where(Message.message_id == mid))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_reply_is_natural_language(appdb):
    """Reply must be human-readable, not raw JSON."""
    app, _, _ps = appdb
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/messages", json=_m("RTEST", "TTEST1 ka surge nahi mila"))
    reply = r.json()["reply"]
    assert not reply.strip().startswith("{"), f"Reply is raw JSON: {reply[:80]}"
    assert len(reply) > 10


@pytest.mark.asyncio
async def test_claimed_amount_not_paid(appdb):
    """Rider claims ₹999 — payment must be ≤ ₹25 (actual owed)."""
    app, _, _ps = appdb
    paid = []

    class Cap(MockPaySwift):
        async def initiate_payout(self, rider_id, amount, reference, idempotency_key):
            paid.append(amount); return {"payout_id": "p", "status": "processed"}

    with patch("app.agent.orchestrator.get_payswift_client", return_value=Cap()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/messages", json=_m("RTEST", "TTEST1 mein 999 rupay kam aaye"))
    assert r.status_code == 200
    for amt in paid:
        assert amt <= 25, f"Overpaid ₹{amt}; ₹25 was owed"


@pytest.mark.asyncio
async def test_zero_owed_no_payment(appdb):
    """TTEST3 is fully paid — PaySwift must not be called."""
    app, _, _ps = appdb
    called = []

    class Cap(MockPaySwift):
        async def initiate_payout(self, rider_id, amount, reference, idempotency_key):
            called.append(amount); return {"payout_id": "p", "status": "processed"}

    with patch("app.agent.orchestrator.get_payswift_client", return_value=Cap()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/messages", json=_m("RTEST", "TTEST3 ka payout check karo"))
    assert r.status_code == 200
    assert called == [], f"Should not pay; called with {called}"


@pytest.mark.asyncio
async def test_payswift_timeout_escalates(appdb):
    """Timeout → reconcile None → dispute ESCALATED."""
    app, Session, _ps = appdb
    with patch("app.agent.orchestrator.get_payswift_client", return_value=TimeoutPaySwift()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/messages", json=_m("RTEST", "TTEST1 surge missing"))
    assert r.status_code == 200
    from app.models.dispute import Dispute
    from sqlalchemy import select
    async with Session() as s:
        esc = (await s.execute(
            select(Dispute).where(Dispute.rider_id == "RTEST", Dispute.status == "ESCALATED")
        )).scalars().all()
    assert len(esc) >= 1


@pytest.mark.asyncio
async def test_payswift_timeout_reconciled_as_paid(appdb):
    """Timeout → reconcile finds payout → dispute PAID."""
    app, Session, _ps = appdb
    with patch("app.agent.orchestrator.get_payswift_client",
               return_value=TimeoutThenFoundPaySwift()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/messages", json=_m("RTEST", "TTEST1 surge nahi mila"))
    assert r.status_code == 200
    from app.models.payment import Payment
    from sqlalchemy import select
    async with Session() as s:
        paid = (await s.execute(
            select(Payment).where(Payment.rider_id == "RTEST", Payment.status == "COMPLETED")
        )).scalars().all()
    assert len(paid) == 1
    assert paid[0].payswift_payout_id == "pout_reconciled"


@pytest.mark.asyncio
async def test_trip_not_owned_no_payment(appdb):
    """Rider claiming another rider's trip gets rejected; no payment."""
    app, Session, _ps = appdb
    # Seed a different rider with no trips
    from app.models.rider import Rider
    async with Session() as s:
        s.add(Rider(rider_id="RWRONG", name="W", city="B",
                    joined_on=datetime.date(2024, 1, 1)))
        await s.commit()
    called = []

    class Cap(MockPaySwift):
        async def initiate_payout(self, rider_id, amount, reference, idempotency_key):
            called.append(amount); return {"payout_id": "p", "status": "processed"}

    with patch("app.agent.orchestrator.get_payswift_client", return_value=Cap()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/messages", json=_m("RWRONG", "TTEST1 ka surge nahi mila"))
    assert r.status_code == 200
    assert called == [], "Must not pay for another rider's trip"


@pytest.mark.asyncio
async def test_auto_pay_below_limit(appdb):
    """TTEST1 owes ₹25 → auto-pays exactly ₹25."""
    app, _, _ps = appdb
    paid = []

    class Cap(MockPaySwift):
        async def initiate_payout(self, rider_id, amount, reference, idempotency_key):
            paid.append(amount); return {"payout_id": f"p{amount}", "status": "processed"}

    with patch("app.agent.orchestrator.get_payswift_client", return_value=Cap()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/messages", json=_m("RTEST", "TTEST1 ka surge nahi mila"))
    assert r.status_code == 200
    assert paid == [25], f"Expected [25], got {paid}"


@pytest.mark.asyncio
async def test_repeat_autopay_same_day_requires_approval(appdb):
    """First dispute auto-pays; second same-day dispute → ops approval."""
    app, Session, _ps = appdb
    # Seed a second trip for same rider
    from app.models.trip import Trip
    from app.models.payout_line import PayoutLine
    async with Session() as s:
        s.add(Trip(
            trip_id="TTEST5", rider_id="RTEST",
            started_at=datetime.datetime(2026, 9, 20, 12, 0, tzinfo=datetime.timezone.utc),
            status="completed", distance_km=Decimal("6.0"), surge_multiplier=Decimal("1.5"),
        ))
        s.add(PayoutLine(
            line_id="PLTEST5", payout_date=datetime.date(2026, 9, 20),
            rider_id="RTEST", line_type="trip", trip_id="TTEST5", amount=Decimal("49"),
        ))
        await s.commit()

    calls = []

    class Cap(MockPaySwift):
        async def initiate_payout(self, rider_id, amount, reference, idempotency_key):
            calls.append(amount); return {"payout_id": f"p{len(calls)}", "status": "processed"}

    ts = "2026-09-22T09:00:00+05:30"
    with patch("app.agent.orchestrator.get_payswift_client", return_value=Cap()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r1 = await c.post("/messages", json=_m("RTEST", "TTEST1 surge nahi mila",
                                                   mid=f"d1.{uuid.uuid4().hex[:6]}", ts=ts))
            r2 = await c.post("/messages", json=_m("RTEST", "TTEST5 ka bhi surge missing",
                                                   mid=f"d2.{uuid.uuid4().hex[:6]}", ts=ts))
    assert r1.status_code == 200 and r2.status_code == 200
    assert len(calls) <= 1, f"PaySwift called {len(calls)}×; second must go to approval"

    from app.models.approval import Approval
    from sqlalchemy import select
    async with Session() as s:
        pending = (await s.execute(
            select(Approval).where(Approval.rider_id == "RTEST", Approval.status == "PENDING")
        )).scalars().all()
    assert len(pending) >= 1, "Second same-day dispute must be queued for approval"


@pytest.mark.asyncio
async def test_approval_endpoint_idempotent(appdb):
    """POST approve twice → 200 first, 409 second; PaySwift called once."""
    app, Session, _ps = appdb
    from app.models.rider import Rider
    from app.models.conversation import Conversation
    from app.models.dispute import Dispute
    from app.models.approval import Approval
    async with Session() as s:
        conv = Conversation(id=str(uuid.uuid4()), rider_id="RTEST",
                            state="WAITING_FOR_APPROVAL")
        s.add(conv)
        await s.flush()
        disp = Dispute(
            id=str(uuid.uuid4()), rider_id="RTEST", conversation_id=conv.id,
            dispute_type="MISSING_PAYOUT", trip_id="TTEST1",
            delivery_date=datetime.date(2026, 9, 20),
            expected_amount=Decimal("74"), actual_paid=Decimal("49"),
            amount_owed=Decimal("25"), status="WAITING_FOR_APPROVAL",
            agent_notes="test",
        )
        s.add(disp)
        await s.flush()
        appr = Approval(
            id=str(uuid.uuid4()), dispute_id=disp.id, rider_id="RTEST",
            approval_type="approval", amount=Decimal("25"),
            reason="Test", status="PENDING",
        )
        s.add(appr)
        await s.commit()
        appr_id = appr.id

    calls = []

    class Cap(MockPaySwift):
        async def initiate_payout(self, rider_id, amount, reference, idempotency_key):
            calls.append(amount); return {"payout_id": f"p{len(calls)}", "status": "processed"}

    with patch("app.api.operations.get_payswift_client", return_value=Cap()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r1 = await c.post(f"/ops/approvals/{appr_id}/approve",
                              json={"operator_id": "ops", "comments": "ok"})
            r2 = await c.post(f"/ops/approvals/{appr_id}/approve",
                              json={"operator_id": "ops", "comments": "dup"})
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 409, f"Expected 409, got {r2.status_code}"
    assert len(calls) == 1, f"PaySwift called {len(calls)}×; must be exactly 1"
