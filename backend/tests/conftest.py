"""
Shared test infrastructure.

Each test gets a completely isolated in-memory SQLite database via StaticPool.
StaticPool reuses one connection for the entire lifetime of the engine — perfect
for in-memory SQLite which is connection-local.

asyncio_default_*_loop_scope = session (set in pytest.ini) means all tests
and fixtures share one event loop, so the StaticPool connection never crosses
loop boundaries.
"""
import datetime
import os
import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# ── override .env BEFORE any pydantic-settings import ──────────────────────
os.environ["LLM_PROVIDER"] = "mock"
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ.setdefault("PAYSWIFT_BASE_URL", "http://localhost:8081")


# ── mock PaySwift ───────────────────────────────────────────────────────────
class MockPaySwift:
    async def health(self): return True
    async def initiate_payout(self, rider_id, amount, reference, idempotency_key):
        return {"payout_id": f"pout_{uuid.uuid4().hex[:8]}", "status": "processed"}
    async def list_payouts(self, rider_id=None): return []
    async def get_total_paid_to_rider(self, rider_id): return Decimal("0")
    async def verify_trip_payment(self, rider_id, reference_contains): return []
    async def reconcile_uncertain_payment(self, rider_id, idempotency_key): return None


class TimeoutPaySwift(MockPaySwift):
    async def initiate_payout(self, rider_id, amount, reference, idempotency_key):
        from app.core.exceptions import PaySwiftUncertainError
        raise PaySwiftUncertainError("timeout", idempotency_key=idempotency_key)


class TimeoutThenFoundPaySwift(MockPaySwift):
    async def initiate_payout(self, rider_id, amount, reference, idempotency_key):
        from app.core.exceptions import PaySwiftUncertainError
        raise PaySwiftUncertainError("timeout", idempotency_key=idempotency_key)
    async def reconcile_uncertain_payment(self, rider_id, idempotency_key):
        return {"payout_id": "pout_reconciled", "status": "processed", "amount": 25}


class FailPaySwift(MockPaySwift):
    async def initiate_payout(self, rider_id, amount, reference, idempotency_key):
        from app.core.exceptions import PaySwiftError
        raise PaySwiftError("invalid_rider_id")


# ── standard seed ───────────────────────────────────────────────────────────
async def seed_standard(session):
    from app.models.rider import Rider
    from app.models.trip import Trip
    from app.models.payout_line import PayoutLine

    session.add(Rider(rider_id="RTEST", name="Test Rider", city="Bengaluru",
                      joined_on=datetime.date(2024, 1, 1)))
    # TTEST1: 6km 1.5x → ₹74 expected, ₹49 paid, ₹25 owed
    session.add(Trip(
        trip_id="TTEST1", rider_id="RTEST",
        started_at=datetime.datetime(2026, 9, 20, 10, 0, tzinfo=datetime.timezone.utc),
        status="completed", distance_km=Decimal("6.0"), surge_multiplier=Decimal("1.5"),
    ))
    session.add(PayoutLine(
        line_id="PLTEST1", payout_date=datetime.date(2026, 9, 20),
        rider_id="RTEST", line_type="trip", trip_id="TTEST1", amount=Decimal("49"),
    ))
    # TTEST2: 12km 1.0x → ₹85 expected, unpaid
    session.add(Trip(
        trip_id="TTEST2", rider_id="RTEST",
        started_at=datetime.datetime(2026, 9, 21, 10, 0, tzinfo=datetime.timezone.utc),
        status="completed", distance_km=Decimal("12.0"), surge_multiplier=Decimal("1.0"),
    ))
    # TTEST3: 6km 1.5x → ₹74 expected, ₹74 paid (no discrepancy)
    session.add(Trip(
        trip_id="TTEST3", rider_id="RTEST",
        started_at=datetime.datetime(2026, 9, 21, 12, 0, tzinfo=datetime.timezone.utc),
        status="completed", distance_km=Decimal("6.0"), surge_multiplier=Decimal("1.5"),
    ))
    session.add(PayoutLine(
        line_id="PLTEST3", payout_date=datetime.date(2026, 9, 21),
        rider_id="RTEST", line_type="trip", trip_id="TTEST3", amount=Decimal("74"),
    ))
    # TTEST4: cancelled by rider
    session.add(Trip(
        trip_id="TTEST4", rider_id="RTEST",
        started_at=datetime.datetime(2026, 9, 21, 14, 0, tzinfo=datetime.timezone.utc),
        status="cancelled_by_rider", distance_km=Decimal("3.0"),
        surge_multiplier=Decimal("1.0"),
    ))


# ── per-test fixture ─────────────────────────────────────────────────────────
@pytest.fixture()
async def appdb():
    """
    Fresh in-memory SQLite (StaticPool) per test.
    StaticPool uses one connection for the engine lifetime, so the same
    connection is used by both the HTTP handler and the test assertions —
    committed rows are always visible.

    With asyncio_default_*_loop_scope=session in pytest.ini, the engine
    never crosses event-loop boundaries.
    """
    import app.tools.payswift_client as psmod
    from app.agent.llm_client import MockLLMClient
    from app.database import Base, get_db
    from app.main import app
    from app.config import get_settings

    get_settings.cache_clear()
    psmod._client = None
    mock_ps = MockPaySwift()
    mock_llm = MockLLMClient()

    # In-memory SQLite with StaticPool — one connection shared across sessions
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, checkfirst=True))

    Session = async_sessionmaker(
        engine, class_=AsyncSession,
        expire_on_commit=False, autocommit=False, autoflush=False,
    )

    # Seed base data
    async with Session() as s:
        await seed_standard(s)
        await s.commit()

    # Wire into FastAPI dependency injection
    async def override_db():
        async with Session() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    app.dependency_overrides[get_db] = override_db

    with patch("app.agent.orchestrator.get_payswift_client", return_value=mock_ps), \
         patch("app.tools.payswift_client.get_payswift_client", return_value=mock_ps), \
         patch("app.api.operations.get_payswift_client", return_value=mock_ps), \
         patch("app.agent.orchestrator.get_llm_client", return_value=mock_llm), \
         patch("app.agent.llm_client.get_llm_client", return_value=mock_llm):
        yield app, Session, mock_ps

    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()
    psmod._client = None
