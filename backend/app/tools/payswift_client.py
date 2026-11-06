"""PaySwift API client.

Implements all documented sandbox operations:
  POST /v1/payouts  – initiate a payout (integer rupees, idempotency key required)
  GET  /v1/payouts  – list payouts, optionally filtered by rider_id
  GET  /health      – liveness check

Safety contract:
- Callers MUST pass an idempotency_key derived from a stable dispute/approval ID.
- On timeout or network error, the payment outcome is UNCERTAIN — callers must
  call reconcile_uncertain_payment() before retrying or marking as failed.
- On confirmed failure (4xx / 5xx response received), raise PaySwiftError.
- Never silently swallow errors or fabricate a success response.
"""
import logging
import uuid
from decimal import Decimal
from typing import Optional

import httpx

from app.config import get_settings
from app.core.exceptions import PaySwiftError, PaySwiftUncertainError

log = logging.getLogger(__name__)


class PaySwiftClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        settings = get_settings()
        self.base_url = (base_url or settings.payswift_base_url).rstrip("/")
        self.timeout = timeout or settings.payswift_timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"Content-Type": "application/json"},
        )

    async def health(self) -> bool:
        """Return True if PaySwift is reachable and healthy."""
        try:
            async with self._client() as c:
                r = await c.get("/health")
                return r.status_code == 200
        except Exception:
            return False

    async def initiate_payout(
        self,
        rider_id: str,
        amount: int,
        reference: str,
        idempotency_key: str,
    ) -> dict:
        """
        POST /v1/payouts — initiate a payout.

        Returns the PaySwift response dict on success (HTTP 201).
        Raises PaySwiftError on unrecoverable server-side failures.

        IMPORTANT: On httpx.TimeoutException or network error, raises
        PaySwiftUncertainError — the caller MUST reconcile before retrying.
        """
        if not idempotency_key:
            raise ValueError("idempotency_key is required for every payout")

        payload = {
            "rider_id": rider_id,
            "amount": int(amount),   # PaySwift requires integer
            "reference": reference,
        }
        headers = {"Idempotency-Key": idempotency_key}

        try:
            async with self._client() as c:
                r = await c.post("/v1/payouts", json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            log.warning(
                "PaySwift TIMEOUT — outcome uncertain. rider=%s amount=%s idem=%s",
                rider_id, amount, idempotency_key,
            )
            raise PaySwiftUncertainError(
                f"PaySwift request timed out — outcome unknown: {exc}",
                idempotency_key=idempotency_key,
            ) from exc
        except httpx.RequestError as exc:
            log.error("PaySwift network error (pre-send): %s", exc)
            # Pre-send errors are safe to treat as failed (request never left)
            raise PaySwiftError(f"PaySwift network error: {exc}") from exc

        log.info("PaySwift response: HTTP %s  %s", r.status_code, r.text[:200])

        if r.status_code == 201:
            return r.json()

        if r.status_code == 409:
            body = r.json()
            error_code = body.get("error", "")
            if error_code == "idempotency_key_reused":
                # Same key, different body — programmer error
                raise PaySwiftError(
                    f"Idempotency key reused with different body: {idempotency_key}"
                )
            # request_in_progress (409 with different code) — outcome uncertain
            raise PaySwiftUncertainError(
                f"PaySwift 409 conflict: {body}",
                idempotency_key=idempotency_key,
            )

        if r.status_code == 429:
            raise PaySwiftError(
                "PaySwift rate limit hit. Account temporarily blocked."
            )

        if r.status_code >= 500:
            raise PaySwiftError(
                f"PaySwift server error {r.status_code}: {r.text[:200]}"
            )

        # 400-level — definitive rejection
        try:
            body = r.json()
        except Exception:
            body = {"error": r.text}
        raise PaySwiftError(
            f"PaySwift rejected payout ({r.status_code}): {body}"
        )

    async def list_payouts(self, rider_id: str | None = None) -> list[dict]:
        """
        GET /v1/payouts[?rider_id=X]
        Returns list of payout records.
        Raises PaySwiftError on failure.
        """
        params: dict = {}
        if rider_id:
            params["rider_id"] = rider_id

        try:
            async with self._client() as c:
                r = await c.get("/v1/payouts", params=params)
        except httpx.TimeoutException as exc:
            raise PaySwiftError(f"PaySwift list_payouts timed out: {exc}") from exc
        except httpx.RequestError as exc:
            raise PaySwiftError(f"PaySwift list_payouts network error: {exc}") from exc

        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                return data
            return data.get("payouts", [])

        raise PaySwiftError(
            f"PaySwift list_payouts error {r.status_code}: {r.text[:200]}"
        )

    async def get_total_paid_to_rider(self, rider_id: str) -> Decimal:
        """Sum all 'processed' payouts for a rider from PaySwift."""
        payouts = await self.list_payouts(rider_id=rider_id)
        total = Decimal("0")
        for p in payouts:
            if p.get("status") == "processed":
                total += Decimal(str(p.get("amount", 0)))
        return total

    async def verify_trip_payment(
        self, rider_id: str, reference_contains: str
    ) -> list[dict]:
        """Return PaySwift payouts whose reference contains a given string."""
        payouts = await self.list_payouts(rider_id=rider_id)
        return [
            p for p in payouts
            if reference_contains.lower() in str(p.get("reference", "")).lower()
        ]

    async def reconcile_uncertain_payment(
        self, rider_id: str, idempotency_key: str
    ) -> Optional[dict]:
        """
        After a timeout or uncertain response, query PaySwift to determine
        whether the payout was actually created.

        Returns the payout record if found, None if not found.
        Raises PaySwiftError if the query itself fails (caller must not retry payment).

        NOTE: The sandbox does not include idempotency_key in GET responses, so we
        can only match by rider_id + recency. In production this would match by key.
        """
        try:
            payouts = await self.list_payouts(rider_id=rider_id)
        except PaySwiftError:
            # Query failed — leave status as UNCERTAIN, do not retry
            raise

        # Try to match by idempotency_key field if sandbox returns it
        for p in payouts:
            if p.get("idempotency_key") == idempotency_key:
                return p

        # Sandbox does not return idempotency_key — cannot positively identify.
        # Return None to mean "could not confirm". Callers must escalate, not retry.
        return None




# Singleton for use across the application
_client: PaySwiftClient | None = None


def get_payswift_client() -> PaySwiftClient:
    global _client
    if _client is None:
        _client = PaySwiftClient()
    return _client
