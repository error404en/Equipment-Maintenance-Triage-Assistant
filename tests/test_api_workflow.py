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


def test_create_work_order_success_and_audit(test_client: TestClient, db_session: Session) -> None:
    _eq, report = _setup_base_data(db_session)
    payload = {
        "priority": 1,
        "proposed_steps": "Fix it",
        "findings": [
            {
                "kind": "possible_cause",
                "source": "ai",
                "description": "Maybe bad motor",
                "citations": []
            }
        ]
    }
    response = test_client.post(f"/api/reports/{report.id}/work-orders", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "draft"

    wo_id = data["id"]
    audit = db_session.query(AuditLog).filter(AuditLog.entity_type == "work_order", AuditLog.entity_id == wo_id).first()
    assert audit is not None
    assert audit.action == "created"


def test_create_work_order_validates_finding(test_client: TestClient, db_session: Session) -> None:
    _eq, report = _setup_base_data(db_session)
    # Try to submit a confirmed finding from AI, which should fail
    payload = {
        "priority": 1,
        "findings": [
            {
                "kind": "confirmed",
                "source": "ai",
                "description": "AI confirms it",
                "citations": []
            }
        ]
    }
    response = test_client.post(f"/api/reports/{report.id}/work-orders", json=payload)
    assert response.status_code == 422


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
