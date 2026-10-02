import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass

class Equipment(Base):
    __tablename__ = "equipment"
    id = Column(Integer, primary_key=True, index=True)
    identifier = Column(String, unique=True, nullable=False, index=True)
    type = Column(String, nullable=False)

class IssueReport(Base):
    __tablename__ = "issue_report"
    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False)
    reported_by = Column(String, nullable=False)
    description = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    equipment = relationship("Equipment")

class ReportEvent(Base):
    __tablename__ = "report_event"
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("issue_report.id"), nullable=False)
    event_index = Column(Integer, nullable=False)
    readings = Column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint("report_id", "event_index", name="uq_report_event_index"),
    )

class Finding(Base):
    __tablename__ = "finding"
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("issue_report.id"), nullable=False)
    kind = Column(String, nullable=False)
    source = Column(String, nullable=False)
    description = Column(String, nullable=False)
    citations = Column(JSONB, nullable=False, default=list)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('observation', 'possible_cause', 'confirmed')",
            name="chk_finding_kind"
        ),
        CheckConstraint(
            "source IN ('ai', 'rules', 'technician')",
            name="chk_finding_source"
        ),
        CheckConstraint(
            "kind != 'confirmed' OR source = 'technician'",
            name="chk_finding_confirmed_technician"
        ),
    )

class WorkOrder(Base):
    __tablename__ = "work_order"
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("issue_report.id"), nullable=False)
    status = Column(String, nullable=False)
    priority = Column(Integer, nullable=False)
    proposed_steps = Column(String, nullable=True)
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'approved', 'rejected')",
            name="chk_work_order_status"
        ),
        CheckConstraint(
            "(status = 'draft' AND reviewed_by IS NULL AND reviewed_at IS NULL) OR "
            "(status != 'draft' AND reviewed_by IS NOT NULL AND reviewed_by != '' AND reviewed_at IS NOT NULL)",
            name="chk_work_order_review"
        ),
    )

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(Integer, nullable=False)
