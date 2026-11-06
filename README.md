# Rider Payout Dispute Desk

AI-powered payout dispute resolution for QuickDrop (~5,000 riders). Riders send complaints over WhatsApp; the system understands, verifies, and resolves them automatically or routes to ops.

## Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, PostgreSQL
- **AI**: Groq API (llama-3.3-70b-versatile) or Google Gemini, with MockLLMClient for tests
- **Payment**: PaySwift sandbox (provided, unchanged)
- **Frontend**: React 18, Vite, Tailwind CSS, Recharts, React Router
- **Infra**: Docker Compose, GitHub Actions CI

## Environment Variables

Copy `.env.example` to `.env` and set:

```
LLM_PROVIDER=groq          # or gemini
GROQ_API_KEY=gsk_...       # Groq API key
GEMINI_API_KEY=...         # Optional: Gemini key
```

All other variables default correctly for Docker Compose.

## Start with Docker Compose

```bash
cp .env.example .env
# Add your GROQ_API_KEY (or GEMINI_API_KEY) to .env
docker compose up --build
```

Services: **Frontend** → http://localhost:5173 | **Backend** → http://localhost:8000 | **PaySwift** → http://localhost:8081

## Dashboard

Open http://localhost:5173. Pages: Dashboard overview, Conversations, Disputes, Pending Approvals (approve/reject), Escalations.

## Agent Architecture

**LLM decides**: intent classification (MISSING_SURGE, MISSING_INCENTIVE, etc.), entity extraction (trip IDs, dates), missing info detection, natural language replies.

**Deterministic backend decides**: trip lookup, expected payout calculation (₹25 base + ₹6/km after 2km × surge), PaySwift actual payment verification, amount owed (`max(0, expected − actual)`), auto-pay eligibility (≤₹200, once/day), human approval routing, payment execution, audit trail.

**Tools**: `trip_lookup`, `payout_calculator`, `payswift_client`, `policy_checker`, `conversation_manager`.

## Payment Safety

- Auto-pay capped at ₹200 per dispute
- Once per rider per day for auto-pay; repeat → ops approval
- Payment only after PaySwift confirms success
- Idempotency keys on every PaySwift call
- Duplicate message IDs return stored reply without re-processing
- Never uses rider's claimed amount — always calculated from trip data
- Suspicious/injection messages escalated, never paid

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/messages` | Receive rider message, return reply |
| GET | `/trace/{rider_id}` | Full chronological agent audit trail |
| GET | `/ops/pending` | Pending approvals and escalations |
| POST | `/ops/approvals/{id}/approve` | Approve payment (re-validates before paying) |
| POST | `/ops/approvals/{id}/reject` | Reject with mandatory comments |
| GET | `/ops/conversations` | All conversations |
| GET | `/ops/disputes` | All disputes |
| GET | `/ops/stats` | Dashboard aggregate stats |
| GET | `/health` | Service liveness |

## Evaluation

```bash
pip install requests
python evals/run_evals.py --base-url http://localhost:8000
```

20 scenarios: valid payouts, approval thresholds, duplicate webhooks, incentives, multi-message conversations, suspicious messages, payment safety, end-to-end resolution.

## Assumptions

- "Day" for daily limits and incentives = calendar day in IST (UTC+5:30)
- Trip `T312538` distance `5000` in CSV is treated as `5.0km` (decimal separator artifact)
- Dispute window = 7 days from message received_at date
- PaySwift `GET /v1/payouts?rider_id=X` is used for reconciliation
- Conversations persist across sessions; a new conversation starts only after the previous one is RESOLVED/REJECTED

## Known Limitations

- Concurrency lock for the "once per day" rule uses DB query (not SELECT FOR UPDATE); very high concurrency could race — acceptable for the current scale
- PaySwift GET /v1/payouts does not return idempotency_key in responses, so `reconcile_uncertain_payment` matches by rider_id only
- Frontend approval uses `operator_id: "ops_user"` placeholder (no auth system)
- Gemini client uses deprecated `google-generativeai`; upgrade to `google.genai` if needed
