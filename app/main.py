import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload

from app.ai import LLMProvider
from app.analysis import run_analysis
from app.db import get_db
from app.models import IssueReport, ReportEvent
from app.retrieval import load_knowledge_base
from app.schemas import AnalysisResponse

app = FastAPI(title="Equipment Triage Assistant")

# Global dependencies
KB_DIR = Path(os.path.join(os.path.dirname(__file__), "kb"))
global_retriever = load_knowledge_base(KB_DIR)

def get_llm_provider() -> LLMProvider | None:
    # Default production behavior: No paid API configured.
    return None

@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


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
        provider=llm_provider,
    )

# Serve the built frontend
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):  # type: ignore
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
