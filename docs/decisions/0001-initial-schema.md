# Initial Schema and Constraints

**Context**: We need to define the foundational database schema for the Equipment Triage Assistant, ensuring project invariants are enforced strictly at the database level.

**Decision**:
We chose to implement the following tables and strict constraints using Postgres `CHECK` constraints via SQLAlchemy:
- `equipment`: `identifier` must be unique.
- `issue_report`: Associates issues to equipment.
- `report_event`: Has a `UNIQUE(report_id, event_index)` constraint to provide stable anchors for AI citations.
- `finding`: Uses JSONB for `citations` to avoid a separate junction table. Enforces `kind` in `('observation', 'possible_cause', 'confirmed')` and `source` in `('ai', 'rules', 'technician')`. Crucially, enforces `CHECK (kind != 'confirmed' OR source = 'technician')` to guarantee the AI never creates confirmed findings.
- `work_order`: Enforces `status` in `('draft', 'approved', 'rejected')`. Additionally enforces that if `status = 'draft'`, `reviewed_by` must be NULL, and if approved/rejected, `reviewed_by` must NOT be NULL.
- `audit_log`: Used for append-only records of actions.

**Alternatives Considered**:
- Creating a separate table for `citations`. Rejected for now to keep the schema simple via JSONB arrays, as citations are only read sequentially.
- Enforcing rules only in Python (FastAPI/Pydantic). Rejected because database-level enforcement provides the strongest safety guarantee against bad data.

**Consequences**:
- AI and rules engine output will instantly crash if they violate constraints, requiring careful validation logic in the application layer.
- Migration scripts will include raw SQL for CHECK constraints where SQLAlchemy's high-level API might fall short.
