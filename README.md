# Equipment Maintenance Triage Assistant

A deterministic-first, AI-assisted web application for triaging equipment faults.

When a maintenance technician logs an equipment fault, the system:
1. Runs deterministic threshold checks (e.g., verifying sensor readings).
2. Retrieves relevant manual sections using BM25.
3. Proposes possible causes, inspection steps, and a draft work order using an optional, guarded LLM step.
4. Allows a human to edit, approve, or reject the work order.

## Architecture & Boundaries

**Layered Design:**
- **Routes (`app/main.py`):** Thin endpoints for parsing, validating, and returning data.
- **Logic (`app/analysis.py`, `app/workflow.py`):** Pure state machines and orchestration. No direct DB I/O.
- **Rules (`app/rules.py`):** Pure threshold engine.
- **Frontend (`frontend/`):** React + Vite SPA using standard Tailwind CSS.

**AI Safety Boundaries:**
- **Invariants:** AI can only create `observation` or `possible_cause` findings. It can never create `confirmed` findings.
- **No Auto-Approval:** Work orders are strictly human-in-the-loop (`draft -> approved | rejected`).
- **Deterministic Precedence:** Thresholds and rule priorities are deterministic. AI can raise priority, but never lower it below the rule-based minimum.
- **Verified Citations:** Every AI suggestion must cite a verified knowledge-base chunk or an event index.
- **Fallback:** If AI is disabled or fails, the application gracefully degrades to rules-only mode.
- **Read-only AI:** AI has no control over equipment.

## Setup

### Prerequisites
- Python 3.12+
- Node.js 20+
- Docker & Docker Compose

### 1. Database Startup
Start the PostgreSQL database and the API using Docker Compose:
```bash
make dev
```
*(Alternatively, run `docker compose up -d db` to just start the database in the background).*

### 2. Migrations
Run Alembic to apply the initial database schema (if not using `make dev` which rebuilds containers, or if running locally):
```bash
source .venv/Scripts/Activate.ps1  # Windows
# source .venv/bin/activate       # Unix
alembic upgrade head
```

### 3. Seed Demo Data
Populate the database with a realistic CNC M-204 demo report and associated events:
```bash
python -m app.kb.seed
```
This is idempotent and can be safely re-run.

### 4. Backend/Frontend Startup
If not using the unified `make dev` container, start the backend and frontend separately:

**Backend:**
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev -- --port 5173
```
Open `http://localhost:5173/` in your browser.

## Tests and Checks

To run all unit tests, integration tests, static typing, and frontend linting/building, use the unified `make check` target:

```bash
make check
```

You can also run tests independently:
```bash
make test  # runs pytest
```
