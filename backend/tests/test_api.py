"""
API integration tests.
Each test creates its own AsyncClient inside the test body
to avoid connection leaks across the async fixture yield.
"""
import datetime
import uuid
import pytest
from httpx import AsyncClient, ASGITransport


def _m(rider_id, text, mid=None, ts="2026-09-22T09:00:00+05:30"):
    return {
        "message_id": mid or f"api.{uuid.uuid4().hex[:8]}",
        "rider_id": rider_id,
        "text": text,
        "received_at": ts,
    }


@pytest.mark.asyncio
async def test_health(appdb):
    app, _, _ps = appdb
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/health")
    assert r.status_code == 200
    assert "status" in r.json()


@pytest.mark.asyncio
async def test_post_message_returns_reply(appdb):
    app, _, _ps = appdb
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/messages", json=_m("RTEST", "TTEST1 ka surge nahi mila"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "reply" in body
    assert len(body["reply"]) > 5
    # Reply must NOT be raw JSON
    assert not body["reply"].strip().startswith("{"), "Reply must be natural language, not raw JSON"


@pytest.mark.asyncio
async def test_duplicate_message_idempotent(appdb):
    app, Session, _ps = appdb
    payload = _m("RTEST", "payout check karo", mid="api.dup.001")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.post("/messages", json=payload)
        r2 = await c.post("/messages", json=payload)
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    assert "reply" in r1.json()
    assert "reply" in r2.json()
    # Exactly one row in DB
    from app.models.message import Message
    from sqlalchemy import select
    async with Session() as s:
        rows = (await s.execute(
            select(Message).where(Message.message_id == "api.dup.001")
        )).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_trace_returns_ordered_events(appdb):
    app, _, _ps = appdb
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/messages", json=_m("RTEST", "TTEST1 ka paisa check karo",
                                         mid="api.trace.001"))
        r = await c.get("/trace/RTEST")
    assert r.status_code == 200
    trace = r.json()
    assert isinstance(trace, list)
    assert len(trace) > 0
    for field in ("at", "type", "name", "input", "output"):
        assert field in trace[0], f"trace step missing: {field}"
    times = [s["at"] for s in trace]
    assert times == sorted(times), "trace not chronological"


@pytest.mark.asyncio
async def test_ops_pending_returns_list(appdb):
    app, _, _ps = appdb
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/ops/pending")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_ops_stats_schema(appdb):
    app, _, _ps = appdb
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/ops/stats")
    assert r.status_code == 200
    data = r.json()
    for key in ("total_disputes", "resolved_disputes", "pending_approvals",
                "escalated_disputes", "total_amount_owed", "total_amount_paid"):
        assert key in data, f"stats missing: {key}"


@pytest.mark.asyncio
async def test_vague_message_asks_for_info(appdb):
    app, _, _ps = appdb
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/messages", json=_m("RTEST", "payout galat hai"))
    assert r.status_code == 200, r.text
    assert len(r.json()["reply"]) > 5


@pytest.mark.asyncio
async def test_ops_conversations_list(appdb):
    app, _, _ps = appdb
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/messages", json=_m("RTEST", "TTEST1 ka surge check karo"))
        r = await c.get("/ops/conversations")
    assert r.status_code == 200
    convs = r.json()
    assert len(convs) >= 1
    for f in ("id", "rider_id", "state", "message_count", "dispute_count", "last_activity"):
        assert f in convs[0]


@pytest.mark.asyncio
async def test_ops_disputes_list(appdb):
    app, _, _ps = appdb
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/messages", json=_m("RTEST", "TTEST1 ka surge nahi mila",
                                         mid="api.disp.001"))
        r = await c.get("/ops/disputes")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
