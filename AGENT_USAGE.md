# Agent Usage Documentation

This document outlines how autonomous agents and Large Language Models (LLMs) were utilized throughout the development, verification, and runtime of the Equipment Maintenance Triage Assistant. It serves as a transparent record of what work was delegated to AI, how failures were mitigated, and how strict invariants were maintained.

## 1. Tools Used During Development and Verification

During the creation of this project, the following agentic tools and environments were leveraged:
- **Terminal Execution (`run_command`)**: Used extensively to run `make check` (triggering `pytest`, `mypy`, `ruff`), execute Alembic schema migrations (`alembic upgrade head`), and manage the local Docker Compose environment.
- **File System Operations (`view_file`, `replace_file_content`, `write_to_file`)**: Used to rapidly iterate on backend Python logic, craft the React component tree, and orchestrate configurations across `.env`, `docker-compose.yml`, and `pyproject.toml`.
- **Browser Subagent (`Playwright` via MCP)**: Acted as an automated browser interface to conduct E2E visual tests. It was used to navigate to `http://localhost:8000/`, wait for the UI to load, interact with the frontend, and capture DOM snapshots. This verified that the AI-generated findings accurately rendered in the frontend without relying purely on backend JSON inspection.

## 2. Representative Prompts Used

### User Prompts to the Development Agent
Development was guided by strict, iterative prompts defining vertical slices of the application. Examples include:
> *"Now integrate Groq as the real LLM provider. Do NOT modify the deterministic rules, database invariants, work-order authorization, or audit behavior. Use an environment variable for the API key... If GROQ_API_KEY is missing, the application must continue in rules-only mode exactly as it does now."*

### Application System Prompts (Runtime LLM)
At runtime, the application queries the Groq API using a highly guarded system prompt explicitly defining boundaries:
> *"You are an industrial equipment diagnostic assistant. You MUST respond ONLY with valid JSON matching this schema: {'findings': [{'kind': 'observation'|'possible_cause', 'description': str, 'citations': [{'chunk_id': str} | {'event_index': int}]}], 'proposed_priority': 0|1|2}. Do not output markdown formatting like ```json, just the raw JSON object. Never output 'confirmed' findings."*

## 3. Work Delegated to the Agent

The development agent autonomously constructed the following vertical slices under the guidance of the invariant rules (`AGENTS.md`):
- **Infrastructure & Scaffold:** Configured `pyproject.toml`, Docker Compose, and Alembic database constraints (e.g., adding `CHECK` constraints to enforce that AI cannot create `confirmed` findings).
- **Deterministic Rules Engine (`app/rules.py`):** Authored the pure Python module handling the threshold rules for sensors, strictly without any I/O or LLM imports.
- **Frontend Assembly:** Built the React single-page application using TypeScript and Vite, translating the backend data structures into a responsive, accessible interface with dedicated visual states for `AI Advisory Engine` health (e.g., OK vs. UNAVAILABLE).
- **Groq Integration & Failover:** Wrote the `GroqLLMProvider` adapter and integrated it safely behind the `LLMProvider` protocol, implementing strict JSON parsing and `try/except` boundaries to handle API failures securely.

## 4. Important AI Mistakes, Rejected Suggestions, and Failures

During the development lifecycle, several AI-driven mistakes and infrastructure failures were encountered and actively resolved:
- **Deprecated Model Endpoints:** When initially integrating Groq, the agent configured the application to use `llama3-70b-8192` and `mixtral-8x7b-32768`. Both resulted in `HTTP 400 - model_decommissioned` and `HTTP 404 - model_not_found` errors. The agent diagnosed the runtime logs and iteratively adapted the configuration to use a supported fallback model (`openai/gpt-oss-120b`).
- **Secret Management Scrutiny:** Secret handling was tightened so real credentials remain outside tracked files; tests use mocked configuration and explicitly verify the no-provider fallback.
- **Playwright Timeout Races:** The E2E Playwright tool initially executed assertions before the Groq API had completed its HTTP response. The agent diagnosed the asynchronous race condition and injected explicit 10-30 second wait commands (`browser_wait_for`) to properly snapshot the DOM after the API hydrated the UI.

## 5. Verification Against Deterministic Rules, Citations, and Approval

The agent built the system to heavily scrutinize the runtime AI output, verifying its integrity via unit tests and structural boundaries:
- **Priority Override Defense:** Tests (e.g., `test_analyze_report_ai_cannot_lower_priority`) were written to explicitly assert that the equation `final_priority = max(rule_priority, AI_proposed)` was respected. If rules declared a priority of `2`, and the AI hallucinates a `0`, the system definitively returns `2`.
- **Citation Validation:** The application backend strips out any citations from the AI that do not match the valid pool of manually retrieved chunks or event indices. Unresolvable citations cause the guarded AI response to fail validation and enter the degraded/unavailable path; they are never rendered as supported evidence.
- **Human In the Loop:** The state machine strictly requires the human operator to transition the work order from `draft` to `approved` or `rejected`. The UI components explicitly state *"AI suggestions are advisory only"* and disable automated transitions.

## 6. Clear Distinction Between Deterministic Business Logic and AI Assistance

The architecture was intentionally segmented to guarantee that generative AI can never usurp hardcoded engineering truths:
- **Deterministic Truths:** Handled entirely by `app/rules.py` and `app/workflow.py`. These modules evaluate sensor readings (e.g., `coolant_temperature`, `spindle_speed`) against predefined ranges. If a sensor reading is missing or conflicting, it is surfaced as an error. The LLM is **never** invoked to guess or interpolate missing sensor data.
- **Advisory Assistance:** Handled by `app/ai.py`. The LLM's role is strictly confined to generating `possible_cause` hypotheses based on the text of the fault report, providing supplementary context (not authoritative rulings). Its outputs are isolated in a specific `ai_findings` array separate from the `rule_results` array. 
- **Graceful Degradation:** If the AI provider experiences an outage or returns malformed data, the orchestrator catches the exception, flags the `ai_status` as `UNAVAILABLE`, and seamlessly serves the authoritative deterministic rule results to the technician so operations are not halted.
