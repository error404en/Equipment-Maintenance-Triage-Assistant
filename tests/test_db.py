from collections.abc import Generator
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import (
    Base,
    Equipment,
    Finding,
    IssueReport,
    ReportEvent,
    WorkOrder,
)

# Connect to the dedicated test database
engine = create_engine(settings.test_database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module")
def setup_database() -> Generator[None, None, None]:
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(setup_database: Any) -> Any:
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()

def test_equipment_unique_identifier(db_session: Any) -> None:
    eq1 = Equipment(identifier="EQ-001", type="pump")
    db_session.add(eq1)
    db_session.commit()

    eq2 = Equipment(identifier="EQ-001", type="compressor")
    db_session.add(eq2)
    with pytest.raises(IntegrityError):
        db_session.commit()

def test_report_event_unique_index(db_session: Any) -> None:
    eq = Equipment(identifier="EQ-002", type="pump")
    db_session.add(eq)
    db_session.commit()

    report = IssueReport(equipment_id=eq.id, reported_by="Alice", description="Test")
    db_session.add(report)
    db_session.commit()

    event1 = ReportEvent(report_id=report.id, event_index=1)
    db_session.add(event1)
    db_session.commit()

    event2 = ReportEvent(report_id=report.id, event_index=1)
    db_session.add(event2)
    with pytest.raises(IntegrityError):
        db_session.commit()

def test_finding_source_constraint(db_session: Any) -> None:
    eq = Equipment(identifier="EQ-003", type="pump")
    db_session.add(eq)
    db_session.commit()
    report = IssueReport(equipment_id=eq.id, reported_by="Alice", description="Test")
    db_session.add(report)
    db_session.commit()

    finding = Finding(
        report_id=report.id,
        kind="observation",
        source="invalid_source",
        description="test",
        citations=[]
    )
    db_session.add(finding)
    with pytest.raises(IntegrityError):
        db_session.commit()

def test_finding_confirmed_requires_technician(db_session: Any) -> None:
    eq = Equipment(identifier="EQ-004", type="pump")
    db_session.add(eq)
    db_session.commit()
    report = IssueReport(equipment_id=eq.id, reported_by="Alice", description="Test")
    db_session.add(report)
    db_session.commit()

    finding = Finding(
        report_id=report.id,
        kind="confirmed",
        source="ai",
        description="test",
        citations=[]
    )
    db_session.add(finding)
    with pytest.raises(IntegrityError):
        db_session.commit()

def test_work_order_review_constraint(db_session: Any) -> None:
    eq = Equipment(identifier="EQ-005", type="pump")
    db_session.add(eq)
    db_session.commit()
    report = IssueReport(equipment_id=eq.id, reported_by="Alice", description="Test")
    db_session.add(report)
    db_session.commit()

    # Draft with a reviewer should fail
    draft = WorkOrder(
        report_id=report.id,
        status="draft",
        priority=1,
        reviewed_by="Bob"
    )
    db_session.add(draft)
    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()

    # Approved without a reviewer should fail
    approved = WorkOrder(
        report_id=report.id,
        status="approved",
        priority=1,
        reviewed_by=None
    )
    db_session.add(approved)
    with pytest.raises(IntegrityError):
        db_session.commit()
