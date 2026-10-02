# AGENTS.md: Equipment Triage Assistant

Read this file fully at the start of every session. It is the project's memory.
If a rule here conflicts with a prompt, stop and ask me.

## What this product does
A web app where a maintenance technician logs an equipment fault. The system
runs deterministic threshold checks, retrieves relevant manual sections, and
uses a guarded LLM step to propose possible causes, follow-up questions,
inspection steps, a priority, and a draft work order. Every suggestion cites its
evidence. A human edits and approves or rejects the work order.
Single tenant. It never controls equipment and never approves work by itself.

## Invariants (enforced in code AND covered by tests; never weaken)
1. **Evidence kinds.** Every finding is `observation`, `possible_cause`, or
   `confirmed`. The AI code path can only create the first two. `confirmed` is
   created only by the technician endpoint. A DB CHECK enforces this too.
2. **No auto-approval.** Work order states: `draft -> approved | rejected` only.
   Approve/reject require a named human actor. Transitions are guarded in SQL
   (`WHERE status = 'draft'`) so double clicks cannot double-approve.
3. **Thresholds are code, not LLM.** `app/rules.py` returns one of
   `ok | warn | critical | missing | conflict` per sensor. A missing reading is
   never guessed or filled in. Conflicts are surfaced, never silently resolved.
4. **Priority is computed.** `final = max(rule_severity, ai_proposed)`. The AI
   can raise priority, never lower it below the rules.
5. **Citations are verified.** Every AI item must cite a retrieved manual chunk
   ID or a real event index from the report. Items with unresolvable citations
   are dropped or shown as "uncited". Never display them as supported.
6. **AI is optional.** With AI disabled or failing, the app still works in
   rules-only mode. Failures are visible: `ai_status = ok | degraded | unavailable`
   plus an error code, shown as a banner. No silent fallbacks, no empty screens.
7. **Audit log is append-only.** Only an append function exists.
8. **No equipment control.** No code path sends commands to any device.

## Stack (defaults I chose; ask before changing)
- Backend: Python 3.12, FastAPI, Pydantic v2
- DB: Postgres (local via docker compose and in production), SQLAlchemy 2.0, Alembic
- Retrieval: BM25 behind a `Retriever` interface (deterministic, no API needed)
- LLM: provider interface with adapters + a `FakeLLM` for tests; JSON output only
- Frontend: React + Vite + TypeScript; API types generated from the backend OpenAPI
- Tooling: ruff, mypy (strict on pure modules), pytest, pre-commit, GitHub Actions
- Delivery: one Docker image; FastAPI serves the built frontend
- Auth: none beyond a named technician identity recorded in the audit log.
  No hand-rolled password handling. Documented as a known limitation.

## Layout and boundaries (current repo is flat; keep it simple)
```
app/
  main.py        thin routes only: parse, validate, call logic, return. No business rules.
  rules.py       PURE threshold engine. No I/O, no DB, no LLM imports.
  workflow.py    PURE work-order state machine + priority combination. No I/O.
  models.py      DB tables and shared types
  db.py          engine/session/repositories
  retrieval.py   (to add) chunking + BM25 behind an interface
  ai.py          (to add) prompt build, LLM call, schema + citation validation, failover
  kb/            manuals as markdown with stable section IDs; seed.py loads demo data
frontend/        React app
tests/           unit / integration / e2e
```
Dependency direction: routes -> logic -> pure modules. Pure modules never import
FastAPI, SQLAlchemy, or an LLM client.

## Working rules
- Plan first, code second. Show me the plan and wait for approval on any new slice.
- One vertical slice per task, one branch per slice, small commits
  (Conventional Commits). Never push to main.
- Write failing tests first from this file, show them failing, then implement.
- **Never edit, delete, or skip a test to make it pass.** If a test exposes a bug,
  stop and report it. Fix the code, not the test.
- Ask before adding any dependency.
- Schema changes only via Alembic migrations. Never edit the DB by hand.
- Validate all input at the boundary. One error format `{error: {code, message}}`.
  Never return stack traces.
- Structured JSON logs with a request ID. Never log secrets or tokens.
- Secrets only in env vars, documented in `.env.example`. Config is validated at
  startup and fails loudly if something is missing.
- No empty `catch`/`except`. Every failure is handled meaningfully or reported.
- Frontend: every data view has loading, empty, error, and success states.
  Works at 375px. Labels on inputs, keyboard usable.
- Out of scope (do not build): live device integration, predictive models,
  inventory, dispatch, user management, billing, caching layers, extra
  equipment types beyond the three in `kb/`.
- The original assignment text is private. Keep it out of the repo (use the
  gitignored `private/` folder). Write docs and README in our own words.

## Commands
- Dev: `make dev`
- All checks (the gate): `make check` = ruff + mypy + pytest + frontend typecheck/build
- Tests only: `make test`
- Migrate: `alembic upgrade head`
- Seed demo data: `python -m app.kb.seed`

## Slice order
1. Scaffold, Makefile, CI, docker compose, `/health`
2. Schema + Alembic + DB constraints (CHECKs for invariants 1 and 2)
3. `rules.py` with tests (boundaries, missing, conflict, unknown equipment)
4. Knowledge base + retrieval with tests
5. LLM adapters, schema + citation validation, failover, rules-only mode
6. Report -> analysis service and routes
7. Work order workflow, audit log, equipment history
8. Frontend screens, then one end-to-end test
9. Seed demo scenarios (normal, conflicting sensors, AI down), README, deploy

## Definition of done (append to every task)
Before saying a task is done:
1. Run `make check` and show the output.
2. List every file changed and why.
3. List anything skipped, stubbed, mocked, or hard-coded.
4. List assumptions I should confirm.
Do not call work complete if any test fails or is skipped.

## Decisions log
Record each decision in `docs/decisions/NNNN-title.md` (context, decision,
alternatives, consequences) and update this file when a rule changes.