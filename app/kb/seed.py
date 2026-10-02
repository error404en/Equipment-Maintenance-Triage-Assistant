import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import Base, Equipment, IssueReport, ReportEvent


def seed_db() -> None:
    # Ensure tables exist (they should, through alembic, but safe)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        # Seed Equipment
        eq = db.execute(select(Equipment).where(Equipment.id == 1)).scalar_one_or_none()
        if not eq:
            eq = Equipment(id=1, identifier="M-204", type="cnc")
            db.add(eq)
            db.flush()

        # Seed IssueReport
        report = db.execute(select(IssueReport).where(IssueReport.id == 1)).scalar_one_or_none()
        if not report:
            report = IssueReport(
                id=1,
                equipment_id=1,
                reported_by="OPERATOR",
                description="High-pitched spindle noise starts when the spindle accelerates above 1,200 RPM. Noise was not present during idle operation this morning. Coolant level was checked and appears normal.",
                timestamp=datetime.datetime.now(datetime.UTC)
            )
            db.add(report)
            db.flush()

        # Seed Events
        events = [
            ReportEvent(
                report_id=1,
                event_index=1,
                readings={"event_type": "SERVICE RECORD", "message": "Scheduled maintenance completed."}
            ),
            ReportEvent(
                report_id=1,
                event_index=2,
                readings={"event_type": "TECHNICIAN", "message": "Routine spindle inspection completed."}
            ),
            ReportEvent(
                report_id=1,
                event_index=3,
                readings={
                    "event_type": "TECHNICIAN",
                    "message": "Coolant level checked \u2014 within normal range.",
                    "coolant_temperature": 21
                }
            ),
            ReportEvent(
                report_id=1,
                event_index=4,
                readings={
                    "event_type": "OPERATOR",
                    "message": "Reported high-pitched spindle noise during rapid movement.",
                    "spindle_speed": 1240,
                    "vibration": 4.8,
                    "bearing_temperature": 71,
                    "hydraulic_pressure": 151
                }
            )
        ]

        for e in events:
            existing = db.execute(
                select(ReportEvent)
                .where(ReportEvent.report_id == e.report_id, ReportEvent.event_index == e.event_index)
            ).scalar_one_or_none()
            if not existing:
                db.add(e)

        db.commit()

if __name__ == "__main__":
    seed_db()
    print("Database seeded successfully.")
