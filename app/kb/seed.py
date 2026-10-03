import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import Base, Equipment, IssueReport, ReportEvent


def seed_db() -> None:
    # Ensure tables exist (they should, through alembic, but safe)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:

        # 1. CNC Mill
        cnc = db.execute(select(Equipment).where(Equipment.identifier == "M-204")).scalar_one_or_none()
        if not cnc:
            cnc = Equipment(identifier="M-204", type="cnc")
            db.add(cnc)
            db.flush()

        # CNC Normal
        if not db.execute(select(IssueReport).where(IssueReport.description == "Spindle normal operation check.")).scalar_one_or_none():
            rep = IssueReport(equipment_id=cnc.id, reported_by="OPERATOR", description="Spindle normal operation check.", timestamp=datetime.datetime.now(datetime.UTC))
            db.add(rep)
            db.flush()
            db.add(ReportEvent(report_id=rep.id, event_index=1, readings={"message": "All parameters normal.", "spindle_speed": 1200, "vibration": 1.2, "bearing_temperature": 50, "hydraulic_pressure": 150}))

        # CNC Conflict
        if not db.execute(select(IssueReport).where(IssueReport.description == "Spindle high vibration but low temp (Conflict).")).scalar_one_or_none():
            rep = IssueReport(equipment_id=cnc.id, reported_by="OPERATOR", description="Spindle high vibration but low temp (Conflict).", timestamp=datetime.datetime.now(datetime.UTC))
            db.add(rep)
            db.flush()
            db.add(ReportEvent(report_id=rep.id, event_index=1, readings={"message": "High vibration detected but temp is surprisingly low.", "spindle_speed": 1200, "vibration": 5.5, "bearing_temperature": 25, "hydraulic_pressure": 150}))

        # CNC Missing
        if not db.execute(select(IssueReport).where(IssueReport.description == "Spindle check with missing vibration data.")).scalar_one_or_none():
            rep = IssueReport(equipment_id=cnc.id, reported_by="OPERATOR", description="Spindle check with missing vibration data.", timestamp=datetime.datetime.now(datetime.UTC))
            db.add(rep)
            db.flush()
            db.add(ReportEvent(report_id=rep.id, event_index=1, readings={"message": "Speed and temp ok, sensor disconnected.", "spindle_speed": 1200, "bearing_temperature": 55}))

        # 2. Pump
        pump = db.execute(select(Equipment).where(Equipment.identifier == "P-101")).scalar_one_or_none()
        if not pump:
            pump = Equipment(identifier="P-101", type="pump")
            db.add(pump)
            db.flush()

        # Pump Normal
        if not db.execute(select(IssueReport).where(IssueReport.description == "Pump normal operation check.")).scalar_one_or_none():
            rep = IssueReport(equipment_id=pump.id, reported_by="OPERATOR", description="Pump normal operation check.", timestamp=datetime.datetime.now(datetime.UTC))
            db.add(rep)
            db.flush()
            db.add(ReportEvent(report_id=rep.id, event_index=1, readings={"message": "Running smooth.", "flow_rate": 100, "pressure": 45, "vibration": 1.0}))

        # Pump Conflict
        if not db.execute(select(IssueReport).where(IssueReport.description == "Pump high flow but low pressure (Conflict).")).scalar_one_or_none():
            rep = IssueReport(equipment_id=pump.id, reported_by="OPERATOR", description="Pump high flow but low pressure (Conflict).", timestamp=datetime.datetime.now(datetime.UTC))
            db.add(rep)
            db.flush()
            db.add(ReportEvent(report_id=rep.id, event_index=1, readings={"message": "Flow is maxed out but pressure is dropping.", "flow_rate": 150, "pressure": 5, "vibration": 1.2}))

        # Pump Missing
        if not db.execute(select(IssueReport).where(IssueReport.description == "Pump check with missing pressure data.")).scalar_one_or_none():
            rep = IssueReport(equipment_id=pump.id, reported_by="OPERATOR", description="Pump check with missing pressure data.", timestamp=datetime.datetime.now(datetime.UTC))
            db.add(rep)
            db.flush()
            db.add(ReportEvent(report_id=rep.id, event_index=1, readings={"message": "Pressure sensor offline.", "flow_rate": 90, "vibration": 1.1}))

        db.commit()

if __name__ == "__main__":
    seed_db()
    print("Database seeded successfully.")
