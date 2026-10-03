from datetime import datetime
from typing import Any, Literal, Self

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


class ReportEventCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    timestamp: datetime | None = None
    readings: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_numeric_readings(self) -> Self:
        for k, v in self.readings.items():
            if k in ["coolant_temperature", "vibration", "spindle_speed", "hydraulic_pressure", "bearing_temperature"]:
                try:
                    float(v)
                except (ValueError, TypeError):
                    raise ValueError(f"Reading {k} must be numeric, got {v}")
        return self


class IssueReportCreate(BaseModel):
    equipment_type: Literal["cnc"]
    equipment_identifier: str = Field(..., min_length=1)
    reported_by: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1, max_length=2000)
    events: list[ReportEventCreate] = Field(max_length=50)


class ReportEventResponse(BaseModel):
    event_index: int
    readings: dict[str, Any] | None


class IssueReportSummaryResponse(BaseModel):
    id: int
    timestamp: datetime
    description: str


class EquipmentResponse(BaseModel):
    id: int
    identifier: str
    type: str
    latest_reports: list[IssueReportSummaryResponse]


class IssueReportDetailResponse(BaseModel):
    id: int
    equipment_id: int
    reported_by: str
    description: str
    timestamp: datetime
    events: list[ReportEventResponse]
