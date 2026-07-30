# EchoStay

A DB-backed FastAPI + Vite/React synthetic environment for browser-agent tasks, modelling a
short-stay booking site: search + filters, listing detail with a booking/reservation widget,
wishlists, trips, messaging, currency/settings, host dashboard, and a help center with support
tickets.

Data is grounded in a public short-stay listings corpus (listings, hosts, reviews, locations) plus
consistent synthetic bookings/payments/wishlists/messages/notifications/support-tickets, shipped
as a pre-built grounding DB (download-required, below).

## Structure

- `backend/` — FastAPI + SQLModel/SQLite API (`app.py`, `routes.py`, `models.py`, `database.py`)
- `frontend/` — Vite/React SPA (built to `frontend/dist/`, served by the backend)
- `tasks/` — the single test task set (`tasks/test_tasks.jsonl`, 117 tasks; see Tasks §)
- `ENV_FEATURES.txt` — UI feature map for the browser solver
- `run_echostay.sh` — one-shot tmux launcher (single-server SPA + API on :8000)

## Grounding database

The env **relies on the pre-built `echostay.db`** (~21 MB) — it uses the provided DB and does
**NOT** re-seed at runtime.

This database is **not committed to the repository** — download it from the Hugging Face dataset
**[microsoft/Echoverse](https://huggingface.co/datasets/microsoft/Echoverse)** and place it at
`envs/echostay/echostay.db` (see the [top-level README](../../README.md#environments) for the one-shot
command that fetches every env's DB):

```bash
# from the repository root
hf download microsoft/Echoverse echostay/echostay.db --repo-type dataset --local-dir ./envs
# -> envs/echostay/echostay.db
```

`init_db()` only runs `SQLModel.metadata.create_all()` (a no-op on this pre-built DB).

## Build & run

```bash
cd envs/echostay
./run_echostay.sh                     # uv sync + npm build + launch on :8000
# or manually:
uv sync
(cd frontend && npm install && npm run build)
uv run python -m backend.app --host 0.0.0.0 --port 8000 --db ./echostay.db --user 1
```

Open http://localhost:8000. API docs at `/docs`, API under `/api`. The `--user N` flag makes every
request behave as if user N is logged in (there is no login form). The default eval user is
`Alex Johnson` (id `1`).

## Tasks

The env ships a single test set: **`tasks/test_tasks.jsonl` (117 tasks)**.

Every task carries a natural-language `goal`, a `task_type` (`read` / `write` / `read_write`),
and a self-contained `verification_query` (plus `reference_answer` for reads and
`reference_state_change` for writes), so it can be graded directly against the env database.
Tasks exercise search & filters (price/amenities/property-type/rooms/instant-book), wishlist,
booking + host approve/decline, trips, support tickets, and account settings.

## Attribution

**EchoStay** is part of the Echoverse **Echo family** of full-domain worlds — a synthetic lodging
marketplace. Its listing/host/review/location data is grounded on the public
[InsideAirbnb](http://insideairbnb.com/) dataset (© InsideAirbnb, licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); modified to generate synthetic seeds).
See the top-level [README](../../README.md) and [Transparency Note](../../TRANSPARENCY.md) for full
attribution.
