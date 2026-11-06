# Evals

Run with:
```
python evals/run_evals.py --base-url http://localhost:8000
```

20 scenarios covering: valid small payouts, approval thresholds, idempotency, multi-message conversations, duplicate webhooks, suspicious messages, incentive eligibility, payment safety, and end-to-end resolution.

The evaluator only uses the public HTTP interface (`POST /messages`, `GET /trace`, `GET /ops/pending`) and does not import backend code or query PostgreSQL.
