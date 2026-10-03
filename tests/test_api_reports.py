from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db import get_db
from app.main import app
from app.models import Base, Equipment, IssueReport

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


def test_create_valid_report(test_client: TestClient, db_session: Session) -> None:
    payload = {
        "equipment_type": "cnc",
        "equipment_identifier": "M-999",
        "reported_by": "TECH-01",
        "description": "Strange noise from spindle.",
        "events": [
            {"message": "Checked coolant", "readings": {"coolant_temperature": 22.5}},
            {"message": "Vibration started", "readings": {"vibration": 5.1}}
        ]
    }
    response = test_client.post("/api/reports", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    
    # Check DB state
    report = db_session.query(IssueReport).filter_by(id=data["id"]).first()
    assert report is not None
    assert report.equipment.identifier == "M-999"
    assert report.equipment.type == "cnc"
    
    from app.models import ReportEvent
    events_count = db_session.query(ReportEvent).filter_by(report_id=data["id"]).count()
    assert events_count == 2
    
def test_validation_failures(test_client: TestClient) -> None:
    # Missing required fields
    response = test_client.post("/api/reports", json={"equipment_type": "cnc"})
    assert response.status_code == 422
    
    # Description too short
    response = test_client.post("/api/reports", json={
        "equipment_type": "cnc",
        "equipment_identifier": "M-999",
        "reported_by": "TECH-01",
        "description": "",
        "events": []
    })
    assert response.status_code == 422

    # Events exceed limit (if we set 50)
    response = test_client.post("/api/reports", json={
        "equipment_type": "cnc",
        "equipment_identifier": "M-999",
        "reported_by": "TECH-01",
        "description": "Too many events.",
        "events": [{"message": "msg"}] * 51
    })
    assert response.status_code == 422

    # Invalid numeric reading (string instead of float for a known numeric key)
    response = test_client.post("/api/reports", json={
        "equipment_type": "cnc",
        "equipment_identifier": "M-999",
        "reported_by": "TECH-01",
        "description": "Invalid reading.",
        "events": [{"message": "msg", "readings": {"coolant_temperature": "hot"}}]
    })
    assert response.status_code == 422

def test_duplicate_equipment_reuse(test_client: TestClient, db_session: Session) -> None:
    payload = {
        "equipment_type": "cnc",
        "equipment_identifier": "M-888",
        "reported_by": "TECH-01",
        "description": "Issue 1",
        "events": []
    }
    res1 = test_client.post("/api/reports", json=payload)
    assert res1.status_code == 200
    
    payload["description"] = "Issue 2"
    res2 = test_client.post("/api/reports", json=payload)
    assert res2.status_code == 200
    
    # Should only be one equipment M-888
    eq_count = db_session.query(Equipment).filter_by(identifier="M-888").count()
    assert eq_count == 1

def test_unsupported_equipment_type(test_client: TestClient) -> None:
    payload = {
        "equipment_type": "lathe",
        "equipment_identifier": "L-123",
        "reported_by": "TECH-01",
        "description": "Unsupported",
        "events": []
    }
    response = test_client.post("/api/reports", json=payload)
    assert response.status_code == 422

def test_create_and_analyze_e2e(test_client: TestClient) -> None:
    # 1. Create report
    payload = {
        "equipment_type": "cnc",
        "equipment_identifier": "M-E2E",
        "reported_by": "TECH-E2E",
        "description": "spindle noise during rapid movement",
        "events": [{"message": "Event", "readings": {"coolant_temperature": 21}}]
    }
    response = test_client.post("/api/reports", json=payload)
    assert response.status_code == 200
    report_id = response.json()["id"]
    
    # 2. Analyze
    analyze_resp = test_client.post(f"/api/reports/{report_id}/analyze")
    assert analyze_resp.status_code == 200
    data = analyze_resp.json()
    assert data["report_id"] == report_id
    assert len(data["rule_results"]) > 0

def test_get_report(test_client: TestClient) -> None:
    payload = {
        "equipment_type": "cnc",
        "equipment_identifier": "M-GET",
        "reported_by": "TECH-01",
        "description": "Test GET",
        "events": [{"message": "E1", "readings": {"a": 1}}]
    }
    create_res = test_client.post("/api/reports", json=payload)
    assert create_res.status_code == 200
    report_id = create_res.json()["id"]

    get_res = test_client.get(f"/api/reports/{report_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["id"] == report_id
    assert data["description"] == "Test GET"
    assert len(data["events"]) == 1
    assert data["events"][0]["event_index"] == 1
    assert data["events"][0]["readings"]["message"] == "E1"

    get_res_404 = test_client.get("/api/reports/999999")
    assert get_res_404.status_code == 404

def test_get_equipment(test_client: TestClient) -> None:
    res = test_client.get("/api/equipment")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
