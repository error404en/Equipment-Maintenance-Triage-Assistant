import os
from pathlib import Path
from typing import Any, cast

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import update
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import text

from app.ai import LLMProvider
from app.analysis import run_analysis
from app.config import settings
from app.db import append_audit_log, get_db
from app.models import Equipment, Finding, IssueReport, ReportEvent, WorkOrder
from app.retrieval import load_knowledge_base
from app.schemas import (
    AnalysisResponse,
    EquipmentHistoryResponse,
    EquipmentResponse,
    IssueReportCreate,
    IssueReportDetailResponse,
    WorkOrderHistory,
    WorkOrderReview,
)
from app.workflow import InvalidTransitionError, approve_work_order, reject_work_order

app = FastAPI(title="Equipment Triage Assistant")

# CORS — only activated when ALLOWED_ORIGINS is explicitly set.
# In the default single-origin deploy (FastAPI serves the built frontend),
# this middleware is NOT needed and is intentionally skipped.
_cors_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

# Global dependencies
KB_DIR = Path(os.path.join(os.path.dirname(__file__), "kb"))
global_retriever = load_knowledge_base(KB_DIR)

def get_llm_provider() -> LLMProvider | None:
    if settings.groq_api_key:
        from app.ai import GroqLLMProvider
        return GroqLLMProvider(api_key=settings.groq_api_key, model=settings.groq_model)
    # Default production behavior: No paid API configured.
    return None

@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "alive"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)) -> dict[str, Any]:  # noqa: B008
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "components": {"database": "ok"}}
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Database health check failed", exc_info=e)
        raise HTTPException(status_code=503, detail={"status": "degraded", "components": {"database": "unreachable"}})


@app.post("/api/reports/{report_id}/analyze", response_model=AnalysisResponse)
def analyze_report(
    report_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    llm_provider: LLMProvider | None = Depends(get_llm_provider),  # noqa: B008
) -> AnalysisResponse:
    report = (
        db.query(IssueReport)
        .options(joinedload(IssueReport.equipment))
        .filter(IssueReport.id == report_id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    events = (
        db.query(ReportEvent)
        .filter(ReportEvent.report_id == report_id)
        .order_by(ReportEvent.event_index)
        .all()
    )

    return run_analysis(
        report=report,
        events=events,
        retriever=global_retriever,
        db=db,
        provider=llm_provider,
    )


@app.post("/api/reports/{report_id}/draft-work-order", response_model=WorkOrderHistory)
def create_draft_work_order(
    report_id: int,
    db: Session = Depends(get_db),  # noqa: B008
    llm_provider: LLMProvider | None = Depends(get_llm_provider),  # noqa: B008
) -> WorkOrderHistory:
    report = db.query(IssueReport).options(joinedload(IssueReport.equipment)).filter(IssueReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Check if a work order already exists for this report
    existing = db.query(WorkOrder).filter(WorkOrder.report_id == report_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Work order already exists for this report")

    events = db.query(ReportEvent).filter(ReportEvent.report_id == report_id).order_by(ReportEvent.event_index).all()

    analysis = run_analysis(
        report=report,
        events=events,
        retriever=global_retriever,
        db=db,
        provider=llm_provider,
    )

    # Create Findings from AI
    for f in analysis.ai_findings:
        finding = Finding(
            report_id=report_id,
            kind=f.kind,
            source="ai",
            description=f.description,
            citations=[c.model_dump(exclude_none=True) for c in f.citations],
        )
        db.add(finding)

    proposed_steps_parts = []
    if analysis.ai_priority_reason:
        proposed_steps_parts.append(f"Reasoning: {analysis.ai_priority_reason.description}")

    if analysis.ai_questions:
        proposed_steps_parts.append("Questions:")
        for q in analysis.ai_questions:
            proposed_steps_parts.append(f"- {q.description}")

    if analysis.ai_steps:
        proposed_steps_parts.append("Inspection Steps:")
        for s in analysis.ai_steps:
            proposed_steps_parts.append(f"- {s.description}")

    proposed_steps = "\n".join(proposed_steps_parts) if proposed_steps_parts else None

    # Create Work Order
    work_order = WorkOrder(
        report_id=report_id,
        status="draft",
        priority=analysis.final_priority,
        proposed_steps=proposed_steps,
    )
    db.add(work_order)
    db.flush()

    append_audit_log(
        session=db,
        actor="system",
        action="created",
        entity_type="work_order",
        entity_id=int(work_order.id),
    )
    db.commit()
    db.refresh(work_order)

    return WorkOrderHistory(
        id=int(work_order.id),
        status=cast(Any, work_order.status),
        priority=int(work_order.priority),
        proposed_steps=str(work_order.proposed_steps) if work_order.proposed_steps else None,
        reviewed_by=str(work_order.reviewed_by) if work_order.reviewed_by else None,
        reviewed_at=cast(Any, work_order.reviewed_at),
    )


def _review_work_order_db(work_order_id: int, payload: WorkOrderReview, db: Session, action: str) -> WorkOrderHistory:
    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    try:
        if action == "approve":
            updates = approve_work_order(str(work_order.status), payload.actor)
        else:
            updates = reject_work_order(str(work_order.status), payload.actor)
    except InvalidTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Concurrency guard: update only if status is draft
    stmt = (
        update(WorkOrder)
        .where(WorkOrder.id == work_order_id, WorkOrder.status == "draft")
        .values(**updates)
    )
    result = cast(Any, db.execute(stmt))

    if result.rowcount == 0:
        db.rollback()
        raise HTTPException(status_code=409, detail="Work order already reviewed or does not exist")

    append_audit_log(
        session=db,
        actor=payload.actor,
        action="approved" if action == "approve" else "rejected",
        entity_type="work_order",
        entity_id=work_order_id,
    )
    db.commit()

    db.refresh(work_order)
    return WorkOrderHistory(
        id=int(work_order.id),
        status=cast(Any, work_order.status),
        priority=int(work_order.priority),
        proposed_steps=str(work_order.proposed_steps) if work_order.proposed_steps else None,
        reviewed_by=str(work_order.reviewed_by) if work_order.reviewed_by else None,
        reviewed_at=cast(Any, work_order.reviewed_at),
    )


@app.post("/api/work-orders/{work_order_id}/approve", response_model=WorkOrderHistory)
def approve_work_order_route(
    work_order_id: int,
    payload: WorkOrderReview,
    db: Session = Depends(get_db),  # noqa: B008
) -> WorkOrderHistory:
    return _review_work_order_db(work_order_id, payload, db, action="approve")


@app.post("/api/work-orders/{work_order_id}/reject", response_model=WorkOrderHistory)
def reject_work_order_route(
    work_order_id: int,
    payload: WorkOrderReview,
    db: Session = Depends(get_db),  # noqa: B008
) -> WorkOrderHistory:
    return _review_work_order_db(work_order_id, payload, db, action="reject")


@app.get("/api/equipment/{equipment_id}/history", response_model=EquipmentHistoryResponse)
def get_equipment_history(
    equipment_id: int,
    db: Session = Depends(get_db),  # noqa: B008
) -> EquipmentHistoryResponse:
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first()
    if not equipment:
        raise HTTPException(status_code=404, detail="Equipment not found")

    reports = (
        db.query(IssueReport)
        .filter(IssueReport.equipment_id == equipment_id)
        .order_by(IssueReport.timestamp.desc())
        .all()
    )

    work_orders = (
        db.query(WorkOrder)
        .filter(WorkOrder.report_id.in_([r.id for r in reports]) if reports else False)
        .all()
    )
    wo_map = {wo.report_id: wo for wo in work_orders}

    report_histories = []
    for r in reports:
        wo = wo_map.get(int(r.id))
        wo_history = None
        if wo:
            wo_history = WorkOrderHistory(
                id=int(wo.id),
                status=cast(Any, wo.status),
                priority=int(wo.priority),
                proposed_steps=str(wo.proposed_steps) if wo.proposed_steps else None,
                reviewed_by=str(wo.reviewed_by) if wo.reviewed_by else None,
                reviewed_at=cast(Any, wo.reviewed_at),
            )
        report_histories.append({
            "id": int(r.id),
            "reported_by": str(r.reported_by),
            "description": str(r.description),
            "timestamp": r.timestamp,
            "work_order": wo_history,
        })

    return EquipmentHistoryResponse(
        equipment_id=equipment_id,
        equipment_identifier=str(equipment.identifier),
        reports=report_histories,
    )

@app.post("/api/reports", response_model=dict)
def create_report(
    payload: IssueReportCreate,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, int]:
    # Find or create equipment
    equipment = db.query(Equipment).filter(
        Equipment.identifier == payload.equipment_identifier,
        Equipment.type == payload.equipment_type
    ).first()

    if not equipment:
        equipment = Equipment(
            identifier=payload.equipment_identifier,
            type=payload.equipment_type
        )
        db.add(equipment)
        db.flush()

    report = IssueReport(
        equipment_id=equipment.id,
        reported_by=payload.reported_by,
        description=payload.description,
    )
    db.add(report)
    db.flush()

    # Create events
    for i, event_data in enumerate(payload.events, start=1):
        # Merge message and timestamp into readings JSONB
        merged_readings = event_data.readings.copy()
        merged_readings["message"] = event_data.message
        if event_data.timestamp:
            merged_readings["timestamp"] = event_data.timestamp.isoformat()

        report_event = ReportEvent(
            report_id=report.id,
            event_index=i,
            readings=merged_readings,
        )
        db.add(report_event)

    db.flush()

    # Audit log
    append_audit_log(
        session=db,
        actor=payload.reported_by,
        action="created",
        entity_type="issue_report",
        entity_id=int(report.id),
    )

    db.commit()
    return {"id": int(report.id)}


@app.get("/api/reports/{report_id}", response_model=IssueReportDetailResponse)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, Any]:
    report = db.query(IssueReport).filter(IssueReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    events = db.query(ReportEvent).filter(ReportEvent.report_id == report_id).order_by(ReportEvent.event_index).all()

    return {
        "id": int(report.id),
        "equipment_id": int(report.equipment_id),
        "reported_by": str(report.reported_by),
        "description": str(report.description),
        "timestamp": report.timestamp,
        "events": [
            {
                "event_index": int(e.event_index),
                "readings": e.readings
            } for e in events
        ]
    }


@app.get("/api/equipment", response_model=list[EquipmentResponse])
def get_equipment_list(
    db: Session = Depends(get_db),  # noqa: B008
) -> list[dict[str, Any]]:
    equipments = db.query(Equipment).all()

    result: list[dict[str, Any]] = []
    for eq in equipments:
        reports = (
            db.query(IssueReport)
            .filter(IssueReport.equipment_id == eq.id)
            .order_by(IssueReport.timestamp.desc())
            .limit(5)
            .all()
        )

        result.append({
            "id": int(eq.id),
            "identifier": str(eq.identifier),
            "type": str(eq.type),
            "latest_reports": [
                {
                    "id": int(r.id),
                    "timestamp": r.timestamp,
                    "description": str(r.description)
                } for r in reports
            ]
        })

    return result


# Serve the built frontend
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):  # type: ignore
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
