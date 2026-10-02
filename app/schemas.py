from pydantic import BaseModel

from app.ai import AIFinding, AIStatus
from app.rules import RuleResult


class AnalysisResponse(BaseModel):
    report_id: int
    rule_results: list[RuleResult]
    ai_status: AIStatus
    ai_error_code: str | None = None
    ai_findings: list[AIFinding]
    final_priority: int
