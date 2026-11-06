"""
Seed the database from CSV files.

Design: fully idempotent via INSERT ... ON CONFLICT DO NOTHING.
Safe to call on every startup regardless of prior state.
Each table is seeded in its own committed batch — a failure in one
table does not prevent the others from being seeded.
"""
import csv
import datetime
import logging
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"


async def seed_all(db: AsyncSession) -> None:
    """Seed all reference tables. Each table is committed independently."""
    await _seed_table(
        db,
        table="riders",
        csv_file=DATA_DIR / "riders.csv",
        row_fn=_rider_row,
        columns=["rider_id", "name", "city", "joined_on"],
        pk="rider_id",
    )
    await _seed_table(
        db,
        table="trips",
        csv_file=DATA_DIR / "trips.csv",
        row_fn=_trip_row,
        columns=["trip_id", "rider_id", "started_at", "status", "distance_km", "surge_multiplier"],
        pk="trip_id",
    )
    await _seed_table(
        db,
        table="payout_lines",
        csv_file=DATA_DIR / "payout_lines.csv",
        row_fn=_payout_line_row,
        columns=["line_id", "payout_date", "rider_id", "line_type", "trip_id", "amount"],
        pk="line_id",
    )
    log.info("Seeding complete.")


async def _seed_table(
    db: AsyncSession,
    table: str,
    csv_file: Path,
    row_fn,
    columns: list[str],
    pk: str,
) -> None:
    """
    Insert rows from a CSV using INSERT ... ON CONFLICT (pk) DO NOTHING.
    Uses raw SQL for maximum portability across SQLite (tests) and PostgreSQL (production).
    Commits after each batch.
    """
    if not csv_file.exists():
        log.warning("Seed file not found: %s — skipping", csv_file)
        return

    # Build parameterised INSERT ... ON CONFLICT DO NOTHING
    placeholders = ", ".join(f":{c}" for c in columns)
    col_list = ", ".join(columns)
    stmt = text(
        f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
        f"ON CONFLICT ({pk}) DO NOTHING"
    )

    rows = []
    with open(csv_file, newline="", encoding="utf-8") as f:
        for raw in csv.DictReader(f):
            try:
                rows.append(row_fn(raw))
            except Exception as exc:
                log.warning("Skipping bad row in %s: %s — %s", table, raw, exc)

    if not rows:
        log.info("%s: no rows to seed.", table)
        return

    # Execute in batches of 500 to avoid huge transactions
    batch_size = 500
    inserted_total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        try:
            for row in batch:
                await db.execute(stmt, row)
            await db.commit()
            inserted_total += len(batch)
        except Exception as exc:
            await db.rollback()
            log.warning("Batch insert into %s failed: %s — skipping batch", table, exc)

    log.info("Seeded %s: %d rows processed.", table, inserted_total)


# ── Row conversion functions ─────────────────────────────────────────────────

def _rider_row(raw: dict) -> dict:
    return {
        "rider_id": raw["rider_id"].strip(),
        "name": raw["name"].strip(),
        "city": raw["city"].strip(),
        "joined_on": datetime.date.fromisoformat(raw["joined_on"].strip()),
    }


def _trip_row(raw: dict) -> dict:
    started_raw = raw["started_at"].strip().replace("Z", "+00:00")
    dt = datetime.datetime.fromisoformat(started_raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)

    dist = Decimal(raw["distance_km"].strip())
    if dist > 500:
        dist = dist / Decimal("1000")

    return {
        "trip_id": raw["trip_id"].strip(),
        "rider_id": raw["rider_id"].strip(),
        "started_at": dt,                          # native datetime for asyncpg
        "status": raw["status"].strip(),
        "distance_km": str(dist),
        "surge_multiplier": raw["surge_multiplier"].strip(),
    }


def _payout_line_row(raw: dict) -> dict:
    return {
        "line_id": raw["line_id"].strip(),
        "payout_date": datetime.date.fromisoformat(raw["payout_date"].strip()),
        "rider_id": raw["rider_id"].strip(),
        "line_type": raw["line_type"].strip(),
        "trip_id": raw.get("trip_id", "").strip() or None,
        "amount": raw["amount"].strip(),
    }
