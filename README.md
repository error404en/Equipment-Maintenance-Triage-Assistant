# Equipment Maintenance Triage Assistant

A web application that helps a maintenance technician triage an equipment fault: deterministic rule checks come first, manual sections are retrieved with BM25, an optional guarded LLM step adds cited advisory suggestions, and a human approves or rejects the resulting work order.

## Problem / Context

When a machine develops a fault, a technician has to decide how urgent it is, what could be wrong, and what to inspect, usually from a mix of sensor readings, free-text notes, and equipment manuals. Two failure modes matter:

- Readings are missing or inconsistent, and someone guesses.
- A suggestion (human or machine) is acted on without any traceable evidence.

This system addresses both. Thresholds are evaluated by code, not by a model. Every AI suggestion has to cite a retrieved manual section or an event from the report. Nothing becomes an approved work order without a named person doing it.

Technician workflow in this app:

1. Log a fault report (equipment, description, one or more events with sensor readings).
2. Review the deterministic rule results and the cited AI advisory output.
3. Generate a draft work order.
4. Approve or reject it as a named actor.
5. Look at the equipment's report and work-order history.

## What the System Does

```
Technician report
  -> deterministic rules          (app/rules.py)
  -> BM25 knowledge retrieval     (app/retrieval.py)
  -> guarded AI assistance        (app/ai.py, app/analysis.py)
  -> human review
  -> work-order decision          (app/workflow.py)
  -> equipment history + audit log
```

Per analysis request, `run_analysis` in [app/analysis.py](app/analysis.py):

1. Evaluates the deterministic rules for the report's equipment type.
2. Retrieves up to 5 manual chunks with BM25, using the report description as the query and filtering by equipment type.
3. If an LLM provider is configured, builds a prompt (description, events, rule results, retrieved chunks) and calls it through the guarded boundary.
4. Computes the final priority and returns rule results and AI output as separate fields.
5. Records the attempt in the `ai_runs` table (model, status, error code, retrieved chunk IDs, raw output, latency).

## Key Design Principle

```
DATA -> DETERMINISTIC RULES -> AI ASSISTANCE -> HUMAN DECISION
```

- **Deterministic rules are authoritative.** They are plain code with no I/O and no LLM imports.
- **AI is advisory.** It can add hypotheses, questions, and inspection steps, and it can raise priority. It cannot override or replace a rule result, and its output is always marked unconfirmed in the UI.
- **A human decides.** Only a named actor can move a work order out of `draft`.

## Core Safety / AI Guardrails

These are implemented in code. Where a database constraint exists, it is noted.

| Guardrail | How it is enforced |
|---|---|
| AI cannot create `confirmed` findings | The AI response schema only allows `observation` or `possible_cause`. The `finding` table has `CHECK (kind != 'confirmed' OR source = 'technician')`, and the `FindingCreate` schema rejects `confirmed` from any other source. |
| `confirmed` requires a technician | See above. Note: there is currently no endpoint that creates a technician-confirmed finding (see Known Limitations). |
| AI cannot lower deterministic priority | `final_priority = max(rule_max_severity, ai_proposed_priority)` in `run_analysis`. Covered by `test_analyze_report_ai_cannot_lower_priority`. |
| Citations are validated | Every AI item must carry at least one citation. A `chunk_id` must be among the retrieved chunks and an `event_index` must exist in the report. Otherwise validation fails. |
| Invalid AI output does not break triage | Malformed JSON, schema violations, and failed citation checks yield `ai_status = degraded` with an error code (`JSON_PARSE_ERROR`, `SCHEMA_VIOLATION`, `CITATION_VALIDATION_FAILED`). Provider exceptions and a missing provider yield `unavailable` (`PROVIDER_ERROR`, `NO_PROVIDER_CONFIGURED`). Rule results are still returned. |
| Missing sensor values are not guessed | A missing coolant reading produces status `missing`. A reading of `-1.0` is treated as "no reading" and also produces `missing`. |
| Conflicts are surfaced | A non-numeric coolant reading produces status `conflict` (severity 2) rather than being coerced. A non-numeric coolant value is rejected at the API, so `conflict` is currently reachable only through the rule unit tests or data inserted directly. |
| No automatic approval | Work orders start as `draft`. Only the approve/reject endpoints change status, and both require an `actor`. |
| Approval cannot be double-applied | The update is `WHERE id = ? AND status = 'draft'`; a zero-row result returns HTTP 409. |
| Review state is consistent | DB `CHECK` constraints: status is one of `draft/approved/rejected`; a draft has no reviewer; a reviewed order has a non-empty `reviewed_by` and `reviewed_at`. |
| No equipment control | No code path sends commands to any device. |
| Audit log is append-only | The only write path is `append_audit_log` in [app/db.py](app/db.py). |

## Architecture

| Component | Responsibility |
|---|---|
| FastAPI ([app/main.py](app/main.py)) | HTTP routes: parse, validate, delegate, return. Also serves the built frontend and `/health` endpoints. |
| Pydantic ([app/schemas.py](app/schemas.py), [app/ai.py](app/ai.py)) | Request validation (equipment type, numeric readings, length limits) and strict validation of the LLM JSON output (`extra="forbid"`). |
| Rules engine ([app/rules.py](app/rules.py)) | Pure threshold checks returning `RuleResult` objects. |
| Workflow ([app/workflow.py](app/workflow.py)) | Pure work-order state transition logic. |
| Retrieval ([app/retrieval.py](app/retrieval.py)) | Markdown manual chunking and a standard-library BM25 retriever. No network access. |
| AI layer ([app/ai.py](app/ai.py)) | `LLMProvider` protocol, `GroqLLMProvider` adapter, JSON/schema/citation validation, status mapping. |
| Orchestration ([app/analysis.py](app/analysis.py)) | Runs rules, retrieval, AI, and priority combination; persists an `ai_runs` row. |
| PostgreSQL + SQLAlchemy 2.0 + Alembic | Persistence, constraints, and schema migrations (`alembic/`). |
| React + Vite + TypeScript ([frontend/](frontend)) | Single-page UI (equipment list, new report form, analysis/work-order page). Styled with Tailwind CSS 4. |
| Docker | One image: a Node stage builds the frontend, a Python stage runs FastAPI and serves `frontend/dist`. |

Layering: routes call logic, logic calls pure modules. `rules.py` and `workflow.py` do no I/O and import no FastAPI or LLM client. `rules.py` uses the ORM model classes (`app.models`) only as input types. Both are checked with strict mypy.

API endpoints (all defined in [app/main.py](app/main.py)):

| Method | Path | Purpose |
|---|---|---|
| GET | `/health/live` | Liveness; does not touch the database |
| GET | `/health` | Database check; 503 if unreachable |
| GET | `/api/equipment` | List equipment with their latest reports |
| GET | `/api/equipment/{id}/history` | Reports and work-order status for one equipment |
| POST | `/api/reports` | Create a report with events and readings |
| GET | `/api/reports/{id}` | Read a report and its events |
| POST | `/api/reports/{id}/analyze` | Run rules, retrieval, and the AI step |
| POST | `/api/reports/{id}/draft-work-order` | Create a draft work order |
| POST | `/api/work-orders/{id}/approve` | Approve a draft (requires `actor`) |
| POST | `/api/work-orders/{id}/reject` | Reject a draft (requires `actor`) |

## Deterministic Rules

Statuses: `ok`, `warn`, `critical`, `missing`, `conflict`. Each result carries a message, a reason, evidence (event index and reading key), and a severity (0, 1, or 2).

Implemented rules (CNC equipment only; any other equipment type returns no rules):

| Rule | Condition | Result |
|---|---|---|
| `spindle_inspection` | Description contains `spindle noise` (case-insensitive) AND `rapid movement` or `spindle acceleration` appears in the description or in an event reading value (including the event message). | `warn`, severity 1: inspection required before return to production. Otherwise `ok`. |
| `coolant_condition` | Event reading `coolant_temperature`; expected range 18-24 C (inclusive) | In range: `ok`, severity 0. Outside range: `warn`, severity 1. No usable reading (absent, or `-1.0`): `missing`, severity 0. Non-numeric value: `conflict`, severity 2. |

The status enum includes `critical`, but no current rule emits it. The rule layer's severity is the maximum across all rule results.

## Knowledge Retrieval

- Manuals are markdown files in [app/kb/](app/kb): `cnc.md` (spindle inspection, coolant temperature, vibration) and `pump.md` (impeller inspection, bearing temperature).
- Each heading becomes a chunk with a stable ID such as `cnc-spindle-inspection`.
- BM25 (k1 = 1.5, b = 0.75) ranks chunks for the report description, filtered by equipment type. Ties break on chunk ID, so results are deterministic.
- Retrieved chunks are passed to the LLM in the prompt. Their IDs form the set of valid `chunk_id` citations, so the model cannot cite a section that was not retrieved.
- In the UI, a citation to a manual section appears as `[KB: <chunk_id>]`; the detail dialog shows the chunk ID, not the chunk text.
- Retrieval needs no API key and runs even when AI is unavailable.

## AI Behaviour

- **Optional.** If `GROQ_API_KEY` is not set, no provider is created. The app runs rules-only and reports `ai_status = unavailable` with `NO_PROVIDER_CONFIGURED`.
- **Provider failure is contained.** Any exception from the provider is caught and reported as `unavailable` / `PROVIDER_ERROR`; rule results still render.
- **Strict output.** The provider is asked for JSON only (`temperature=0`, JSON response format, 30 s timeout). The reply is parsed and validated against a Pydantic schema with `extra="forbid"`.
- **Cited output.** Findings, follow-up questions, inspection steps, and the priority rationale must all cite retrieved chunks or real event indexes. If any item fails, the whole AI response is rejected and the status is `degraded`; unsupported content is never displayed as supported.
- **Unconfirmed.** AI findings are `observation` or `possible_cause` only. The UI shows AI `possible_cause` findings labelled 'Unconfirmed'. AI `observation` findings are saved with the draft but not shown on the analysis page.
- **Visible status.** The analysis page shows an AI Engine Status badge: OK / DEGRADED / UNAVAILABLE (the error code is shown for UNAVAILABLE).
- **Empty retrieval.** If a provider is configured but nothing was retrieved and there are no events, the status is `degraded` / `EMPTY_RETRIEVAL`.

## Human-in-the-loop Work Orders

```
draft -> approved
draft -> rejected
```

- `POST /api/reports/{id}/draft-work-order` creates a work order in `draft`. Its priority is the computed final priority, and its proposed steps are assembled from the AI rationale, questions, and inspection steps (if any). AI findings are stored as `finding` rows with `source = 'ai'`.
- `POST /api/work-orders/{id}/approve` and `/reject` require a non-empty `actor`. There is no automatic approval path.
- Both are guarded in SQL so a second click cannot re-review the same order (HTTP 409).
- Report creation, draft creation (actor `system`), approval and rejection (named actor) each append an audit entry.
- The actor name is taken from the "Acting as" field in the UI header (default `TECH-04`; can be preset with `?actor=` in the URL). This is a recorded name, not authentication.

## Demo Workflow

Live URL: **[PLACEHOLDER: no deployment URL is recorded in this repository]**

Locally, after `make dev`, open `http://localhost:8000`.

1. Open the app. The home page lists equipment with recent reports (seeded: M-204 CNC and P-101 pump).
2. Select an existing report, or choose New Report (CNC only) and enter an identifier, description, and one or more events with optional readings. The current New Report form exposes three readings: coolant temperature, vibration, and spindle speed.
3. Submit. The app creates the report and runs the analysis automatically.
   - To trigger the spindle warning, put `spindle noise` in the description AND `rapid movement` or `spindle acceleration` in the description or an event message.
   - To trigger the coolant warning, enter a coolant temperature outside 18-24 C, for example 30.
4. Read section 01 (Observations and Facts): deterministic rule results, with `ok / warn / missing / conflict` shown per rule.
5. Read section 02 (AI Analysis, Unconfirmed): check the AI Engine Status badge, then the possible causes, follow-up questions, and inspection steps with their citations.
6. Click "Generate Server Draft Work Order".
7. Review the draft. Use Approve or Reject as the named actor shown in the header.
8. Read the Equipment History Timeline to see the report and its work-order status.

## Example Scenario

The seed data ([app/kb/seed.py](app/kb/seed.py)) creates three CNC reports on equipment `M-204` and three pump reports on `P-101`. Example: the CNC report **"Spindle check with missing vibration data."** has one event: `spindle_speed = 1200`, `bearing_temperature = 55`, message "Speed and temp ok, sensor disconnected."

What the current rules do with it:

- `spindle_inspection`: `ok` (the description does not mention spindle noise during rapid movement).
- `coolant_condition`: `missing` (no `coolant_temperature` reading in any event). The value is not guessed.
- Rule severity is 0, so the final priority is 0 unless the AI raises it.
- Without `GROQ_API_KEY`: `ai_status = unavailable` (`NO_PROVIDER_CONFIGURED`) and the page shows the rule results only.
- With a valid key: the AI may propose causes and steps. Each must cite a retrieved CNC manual chunk or event 1, or the whole AI output is shown as degraded.

Note: the seed scenario names "Conflict" and "Missing" describe the narrative of each report. The rule engine's `conflict` status is only produced by a non-numeric coolant reading, so the seeded "Conflict" reports do not themselves produce a `conflict` rule result. A non-numeric coolant value is rejected at the API, so `conflict` is currently reachable only through the rule unit tests or data inserted directly.

## Running Locally

Prerequisites: Python 3.12+, Node.js 20+, Docker with Compose, `make`.

**Environment variables** (documented in [.env.example](.env.example); copy it to `.env`, which is gitignored):

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL URL, e.g. `postgresql+psycopg://user:password@localhost:5432/triage`. The app exits at startup if it is missing or not a postgres/sqlite URL. |
| `GROQ_API_KEY` | No | Enables the AI step. Without it the app runs rules-only. |
| `GROQ_MODEL` | No | Groq model name. Default `openai/gpt-oss-120b`. |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins. Empty by default (same-origin deployment needs none). |
| `LOG_LEVEL` | No | Read into settings (default `INFO`); not currently applied to any logger. |

`docker-compose.yml` additionally reads `POSTGRES_PASSWORD` (default `postgres`). Tests read `TEST_DATABASE_URL` (default `postgresql+psycopg://postgres:postgres@localhost:5433/triage_test`).

**Python environment** (needed for `alembic`, `python -m app.kb.seed`, `uvicorn`, `pytest`, `ruff`, and `mypy`; not needed for `make dev`, where the container installs it):

```bash
python -m venv .venv
source .venv/bin/activate          # bash / WSL
# .venv\Scripts\Activate.ps1       # Windows PowerShell
# .venv\Scripts\activate.bat       # Windows cmd
pip install -e ".[dev]"
```

`DATABASE_URL` must be configured (in `.env` or the shell) and point at a running Postgres before running `alembic upgrade head` or `python -m app.kb.seed`.

**Commands:**

```bash
make dev                    # docker compose up --build: db, db_test, and the app on :8000
alembic upgrade head        # apply migrations (done automatically in the container)
python -m app.kb.seed       # load demo data (idempotent; also done automatically in the container)
make check                  # ruff + mypy + pytest + frontend lint + frontend build
make test                   # pytest only
```

Running the backend and frontend separately (requires `DATABASE_URL` pointing at a running Postgres, e.g. `docker compose up -d db`):

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
cd frontend && npm install && npm run dev -- --port 5173
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`.

The seed script also calls `Base.metadata.create_all` as a safety net. Alembic remains the migration mechanism.

**Windows note:** the documented shell commands are bash/WSL-style. `make` is required for the Makefile targets, or the commands inside each target can be run manually on Windows. PowerShell 5 users should run chained `&&` commands separately.

## Testing / Verification

`make check` runs, in order: `ruff check .`, `mypy .`, `pytest`, `npm run lint` (oxlint), and `npm run build` (`tsc -b && vite build`). The CI workflow ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs `make check` on pushes and pull requests to `main`, with a Postgres service for the test database.

Backend tests in [tests/](tests):

| File | Covers |
|---|---|
| `test_rules.py` | Spindle and coolant rules, 18/24 boundaries, missing and invalid readings, determinism, evidence, unknown equipment |
| `test_retrieval.py` | Markdown chunking and stable IDs, BM25 ranking, equipment filtering, empty queries, deterministic ordering, no network calls |
| `test_ai.py` | LLM output parsing, schema and citation validation, degraded/unavailable states |
| `test_analysis.py` | Analysis route with and without a provider; AI cannot lower priority |
| `test_api_reports.py` | Report creation and validation, unsupported equipment type, create-and-analyze flow, report and equipment reads |
| `test_api_workflow.py` | Draft work order, AI failure path, approve concurrency, equipment history, audit entries |
| `test_workflow.py` | State machine transitions, named-actor requirement |
| `test_db.py` | DB constraints: unique identifiers, unique event index, finding source and `confirmed` rules, work-order review rules |
| `test_health.py` | `/health` and `/health/live` |

The database tests use a separate Postgres instance (the `db_test` service on port 5433), so start it (`docker compose up -d db_test`) before running `pytest` outside `make dev`.

There are no frontend unit tests. This README does not state a test count.

## Deployment

The repository contains a single [Dockerfile](Dockerfile) (multi-stage) and [docker-compose.yml](docker-compose.yml):

- Stage 1 (`node:20-slim`) installs frontend dependencies and runs `npm run build`.
- Stage 2 (`python:3.12-slim`) installs the Python package, copies `app/`, `alembic/`, and the built `frontend/dist`.
- The container starts with `alembic upgrade head && python -m app.kb.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- FastAPI serves the built frontend, so the app is a single origin.
- `DATABASE_URL` must be provided in the environment. `GROQ_API_KEY` is optional.
- `GET /health/live` returns `{"status": "alive"}` without touching the database. `GET /health` checks the database and returns HTTP 503 with component status if it is unreachable.

`docker-compose.yml` defines the app (`api`), a development Postgres (`db`), and a test Postgres (`db_test`). The repository does not define a specific hosting provider or a production URL, and this README makes no claim about one.

## Known Limitations

- **No real authentication or user management.** The acting technician is a free-text name recorded in the audit log. Anyone who can reach the app can approve or reject a work order.
- **Single tenant.**
- **No live equipment or device integration.** Readings are entered manually; nothing is sent to equipment.
- **No predictive maintenance models.**
- **Limited equipment types.** The knowledge base has CNC and pump manuals only. Rules exist for CNC only, and the new-report API and form accept `cnc` only. Pump data exists only as seed data and has no rules.
- **Technician-confirmed findings are not implemented end to end.** The `confirmed` kind is enforced in the schema and database, but no endpoint or UI action creates one. Section 03 of the analysis page is an empty-state message.
- **Work-order edits are not persisted.** The priority and proposed-steps fields on the analysis page, and the optional reject reason, are local UI state. Approve and reject send only the actor name.
- **Audit log has no read API or UI.** Entries are written but not displayed.
- **Rule coverage is narrow.** Only two CNC rules exist. Conflict detection is limited to non-numeric coolant readings; it does not compare readings across events or sensors. A non-numeric coolant value is rejected at the API, so `conflict` is currently reachable only through the rule unit tests or data inserted directly.
- **Citation failures reject the whole AI response** (status `degraded`) rather than dropping individual items.
- **Draft generation re-runs the analysis.** Generating a draft re-runs the full analysis, including another LLM call and another `ai_runs` record, so drafted content can differ from the analysis the technician previously reviewed.
- **`LOG_LEVEL` is a defined setting only;** this README makes no claim about structured logging or request IDs.
- **Some `AGENTS.md` items are not currently implemented:** the `{error: {code, message}}` response format (the API returns FastAPI's default `detail` errors), OpenAPI-generated frontend types, a pre-commit configuration, and structured JSON logging with request IDs. These are not required for the current working product.
- **Dockerfile installs frontend dependencies from `package.json` only** (the lock file is not copied), so frontend dependency versions are resolved at build time.

## Out of Scope

Per [AGENTS.md](AGENTS.md), the following are intentionally not built: live device integration, predictive models, inventory, dispatch, user management, billing, caching layers, and extra equipment types beyond those in `kb/`.

## Engineering Decisions / Trade-offs

- **Deterministic rules in code.** Thresholds must be reproducible, testable, and independent of a model. Missing and conflicting data have explicit statuses instead of being smoothed over.
- **BM25 instead of embeddings.** It is deterministic, needs no API or vector store, and is easy to test. The trade-off is lexical matching only. It is implemented in a `Retriever` class (no formal interface/protocol yet).
- **Guarded LLM output.** The model is treated as untrusted: JSON only, strict schema, no `confirmed` kind. Failures degrade to rules-only instead of failing the request.
- **Citation validation.** Suggestions are only useful to a technician if they can be traced. Validating against the retrieved chunk IDs and real event indexes prevents invented references. The trade-off is that one bad citation discards the whole AI response.
- **Human approval with DB-level guards.** `CHECK` constraints and a conditional `UPDATE` back up the application checks, so the invariants hold even if application code has a bug. See [docs/decisions/0001-initial-schema.md](docs/decisions/0001-initial-schema.md).

## Submission Notes

This is an assignment/demo system, not a production maintenance platform. Implemented: the report-to-analysis-to-work-order flow described above, two CNC rules, BM25 retrieval over two manuals, an optional Groq-backed AI step with validation, human approve/reject, equipment history, DB constraints, and a Docker image that migrates and seeds on start. Not implemented (future work): authentication, technician-confirmed findings, persisted work-order edits, audit log viewing, additional rules and equipment types, and any device integration.

AI-assisted development is documented in [AGENT_USAGE.md](AGENT_USAGE.md).
