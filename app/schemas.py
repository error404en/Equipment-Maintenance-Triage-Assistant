from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.ai import AIFinding, AIStatus
from app.rules import RuleResult


class AnalysisResponse(BaseModel):
    report_id: int
    equipment_id: int
    rule_results: list[RuleResult]
    ai_status: AIStatus
    ai_error_code: str | None = None
    ai_findings: list[AIFinding]
    final_priority: int


class CitationCreate(BaseModel, extra="forbid"):
    chunk_id: str | None = None
    event_index: int | None = None


class FindingCreate(BaseModel):
    kind: Literal["observation", "possible_cause", "confirmed"]
    source: Literal["ai", "rules", "technician"]
    description: str
    citations: list[CitationCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_confirmed_technician(self) -> Self:
        if self.kind == "confirmed" and self.source != "technician":
            raise ValueError("Only a technician can create a confirmed finding")
        return self


class WorkOrderCreate(BaseModel):
    priority: int
    proposed_steps: str | None = None
    findings: list[FindingCreate]


class WorkOrderReview(BaseModel):
    actor: str


class WorkOrderHistory(BaseModel):
    id: int
    status: Literal["draft", "approved", "rejected"]
    priority: int
    proposed_steps: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None


class ReportHistory(BaseModel):
    id: int
    reported_by: str
    description: str
    timestamp: datetime
    work_order: WorkOrderHistory | None = None


class EquipmentHistoryResponse(BaseModel):
    equipment_id: int
    equipment_identifier: str
    reports: list[ReportHistory]
