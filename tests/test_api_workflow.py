from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db import get_db
from app.main import app
from app.models import AuditLog, Base, Equipment, IssueReport, WorkOrder

# Setup test DB engine
engine = create_engine(settings.test_database_url)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module")
def setup_database() -> Generator[None, None, None]:
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(setup_database: Any) -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def test_client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _setup_base_data(db_session: Session) -> tuple[Equipment, IssueReport]:
    eq = Equipment(identifier=f"EQ-WF-{id(db_session)}", type="cnc")
    db_session.add(eq)
    db_session.commit()

    report = IssueReport(equipment_id=eq.id, reported_by="Test", description="Test description")
    db_session.add(report)
    db_session.commit()
    return eq, report


def test_create_draft_work_order_success_and_audit(test_client: TestClient, db_session: Session) -> None:
    _eq, report = _setup_base_data(db_session)
    # The endpoint will call run_analysis which requires events.
    import json

    from app.main import get_llm_provider
    from app.models import ReportEvent
    from tests.test_ai import FakeLLM

    event = ReportEvent(report_id=report.id, event_index=1, readings={"coolant_temperature": 20})
    db_session.add(event)
    db_session.commit()

    valid_json = json.dumps({
        "findings": [
            {
                "kind": "possible_cause",
                "description": "Bearing failure",
                "citations": [{"event_index": 1}]
            }
        ],
        "follow_up_questions": [
            {"description": "Is the vibration constant?", "citations": [{"event_index": 1}]}
        ],
        "inspection_steps": [
            {"description": "Check bearing", "citations": [{"event_index": 1}]}
        ],
        "priority_reason": {"description": "Noise implies wear.", "citations": [{"event_index": 1}]},
        "proposed_priority": 2
    })

    app.dependency_overrides[get_llm_provider] = lambda: FakeLLM(response_text=valid_json)
    try:
        response = test_client.post(f"/api/reports/{report.id}/draft-work-order")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "draft"
        assert data["priority"] == 2

        # Verify findings are created
        from app.models import Finding
        findings = db_session.query(Finding).filter(Finding.report_id == report.id).all()
        assert len(findings) > 0
        ai_findings = [f for f in findings if f.source == "ai"]
        assert len(ai_findings) == 1
        assert ai_findings[0].description == "Bearing failure"

        wo_id = data["id"]
        audit = db_session.query(AuditLog).filter(AuditLog.entity_type == "work_order", AuditLog.entity_id == wo_id).first()
        assert audit is not None
        assert audit.action == "created"
        assert audit.actor == "system"

        # Verify AI run is persisted
        from app.models import AIRun
        ai_run = db_session.query(AIRun).filter(AIRun.report_id == report.id).first()
        assert ai_run is not None
        assert ai_run.status == "ok"
    finally:
        app.dependency_overrides.clear()


def test_create_draft_work_order_ai_fails(test_client: TestClient, db_session: Session) -> None:
    _eq, report = _setup_base_data(db_session)
    from app.main import get_llm_provider
    from app.models import ReportEvent
    from tests.test_ai import FakeLLM

    event = ReportEvent(report_id=report.id, event_index=1, readings={"coolant_temperature": 20})
    db_session.add(event)
    db_session.commit()

    # Fail the AI
    app.dependency_overrides[get_llm_provider] = lambda: FakeLLM(response_text="invalid json")
    try:
        response = test_client.post(f"/api/reports/{report.id}/draft-work-order")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "draft"

        # Since AI failed, priority should be based on rules (0 in this case)
        assert data["priority"] == 0

        # Verify AI run is persisted as degraded
        from app.models import AIRun
        ai_run = db_session.query(AIRun).filter(AIRun.report_id == report.id).first()
        assert ai_run is not None
        assert ai_run.status == "degraded"
    finally:
        app.dependency_overrides.clear()


def test_approve_work_order_concurrency(test_client: TestClient, db_session: Session) -> None:
    _eq, report = _setup_base_data(db_session)
    wo = WorkOrder(report_id=report.id, status="draft", priority=1)
    db_session.add(wo)
    db_session.commit()

    # First approve
    res1 = test_client.post(f"/api/work-orders/{wo.id}/approve", json={"actor": "Alice"})
    assert res1.status_code == 200
    assert res1.json()["status"] == "approved"

    # Second approve should fail (409)
    res2 = test_client.post(f"/api/work-orders/{wo.id}/approve", json={"actor": "Bob"})
    assert res2.status_code == 409
    assert "Cannot transition from" in res2.json()["detail"]


def test_equipment_history(test_client: TestClient, db_session: Session) -> None:
    eq, report = _setup_base_data(db_session)
    wo = WorkOrder(report_id=report.id, status="draft", priority=1)
    db_session.add(wo)
    db_session.commit()

    res = test_client.get(f"/api/equipment/{eq.id}/history")
    assert res.status_code == 200
    data = res.json()
    assert data["equipment_id"] == eq.id
    assert len(data["reports"]) == 1
    assert data["reports"][0]["id"] == report.id
    assert data["reports"][0]["work_order"]["status"] == "draft"
