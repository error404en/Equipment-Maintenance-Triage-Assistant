import json
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.ai import AIStatus
from app.config import settings
from app.db import get_db
from app.main import app, get_llm_provider
from app.models import Base, Equipment, IssueReport, ReportEvent
from tests.test_ai import FakeLLM

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


def test_analyze_report_no_provider(test_client: TestClient, db_session: Session) -> None:
    # 1. Create DB objects
    eq = Equipment(identifier="EQ-001", type="cnc")
    db_session.add(eq)
    db_session.commit()

    report = IssueReport(equipment_id=eq.id, reported_by="Alice", description="spindle noise")
    db_session.add(report)
    db_session.commit()

    event = ReportEvent(report_id=report.id, event_index=1, readings={"coolant_temperature": 20})
    db_session.add(event)
    db_session.commit()

    # 2. Call without provider override
    response = test_client.post(f"/api/reports/{report.id}/analyze")
    assert response.status_code == 200
    data = response.json()

    assert data["report_id"] == report.id
    assert data["ai_status"] == AIStatus.UNAVAILABLE.value
    assert data["ai_error_code"] == "NO_PROVIDER_CONFIGURED"
    assert data["ai_findings"] == []

    # Priority is just max(rule_severities), let's say rule triggers spindle inspection (WARN -> 1)
    # Wait, spindle rule requires both noise and rapid movement.
    # The event doesn't have rapid movement, so it's 0. Coolant is 20 -> OK -> 0.
    assert data["final_priority"] == 0
    assert len(data["rule_results"]) == 2


def test_analyze_report_with_ai_provider(test_client: TestClient, db_session: Session) -> None:
    # 1. Create DB objects
    eq = Equipment(identifier="EQ-002", type="cnc")
    db_session.add(eq)
    db_session.commit()

    report = IssueReport(equipment_id=eq.id, reported_by="Bob", description="spindle noise during rapid movement")
    db_session.add(report)
    db_session.commit()

    event = ReportEvent(report_id=report.id, event_index=1, readings={"coolant_temperature": 30}) # Coolant out of range -> WARN (1)
    db_session.add(event)
    db_session.commit()

    # Both rules trigger WARN -> rule severity max = 1.

    # AI will return Priority 2.
    valid_json = json.dumps({
        "findings": [
            {
                "kind": "possible_cause",
                "description": "Bearing failure",
                "citations": [{"event_index": 1}]
            }
        ],
        "proposed_priority": 2
    })

    app.dependency_overrides[get_llm_provider] = lambda: FakeLLM(response_text=valid_json)

    try:
        response = test_client.post(f"/api/reports/{report.id}/analyze")
        assert response.status_code == 200
        data = response.json()

        assert data["ai_status"] == AIStatus.OK.value
        assert len(data["ai_findings"]) == 1
        assert data["final_priority"] == 2 # Max of 1 and 2
    finally:
        app.dependency_overrides.clear()


def test_analyze_report_ai_cannot_lower_priority(test_client: TestClient, db_session: Session) -> None:
    eq = Equipment(identifier="EQ-003", type="cnc")
    db_session.add(eq)
    db_session.commit()

    report = IssueReport(equipment_id=eq.id, reported_by="Bob", description="coolant missing")
    db_session.add(report)
    db_session.commit()

    event = ReportEvent(report_id=report.id, event_index=1, readings={"coolant_temperature": "invalid_data"})
    # Invalid coolant reading causes CONFLICT (severity 2)
    db_session.add(event)
    db_session.commit()

    # Rule priority is 2. AI proposes 0.
    valid_json = json.dumps({
        "findings": [],
        "proposed_priority": 0
    })

    app.dependency_overrides[get_llm_provider] = lambda: FakeLLM(response_text=valid_json)

    try:
        response = test_client.post(f"/api/reports/{report.id}/analyze")
        data = response.json()

        assert data["ai_status"] == AIStatus.OK.value
        assert data["final_priority"] == 2 # Remains 2 because max(2, 0)
    finally:
        app.dependency_overrides.clear()


def test_analyze_report_ai_degraded(test_client: TestClient, db_session: Session) -> None:
    eq = Equipment(identifier="EQ-004", type="cnc")
    db_session.add(eq)
    db_session.commit()

    report = IssueReport(equipment_id=eq.id, reported_by="Bob", description="spindle")
    db_session.add(report)
    db_session.commit()

    # LLM returns garbage JSON
    app.dependency_overrides[get_llm_provider] = lambda: FakeLLM(response_text="garbage")

    try:
        response = test_client.post(f"/api/reports/{report.id}/analyze")
        data = response.json()

        assert data["ai_status"] == AIStatus.DEGRADED.value
        assert data["ai_error_code"] == "JSON_PARSE_ERROR"
        assert data["final_priority"] == 0 # Rule priority is 0, AI failed
    finally:
        app.dependency_overrides.clear()


def test_analyze_report_404(test_client: TestClient) -> None:
    response = test_client.post("/api/reports/9999/analyze")
    assert response.status_code == 404
