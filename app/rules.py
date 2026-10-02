from enum import Enum
from typing import Any

from pydantic import BaseModel

from app.models import IssueReport, ReportEvent


class RuleStatus(str, Enum):
    OK = "ok"
    WARN = "warn"
    CRITICAL = "critical"
    MISSING = "missing"
    CONFLICT = "conflict"


class Evidence(BaseModel):
    event_index: int | None = None
    reading_key: str | None = None
    value: Any = None


class RuleResult(BaseModel):
    rule_id: str
    status: RuleStatus
    message: str
    reason: str
    evidence: list[Evidence]
    severity: int = 0


def evaluate_spindle_inspection(report: IssueReport, events: list[ReportEvent]) -> RuleResult:
    """
    Spindle Inspection Rule:
    Condition: spindle noise is reported AND the report/event indicates rapid movement or spindle acceleration.
    """
    desc = report.description.lower() if report.description else ""
    has_spindle_noise = "spindle noise" in desc

    has_rapid_movement = "rapid movement" in desc or "spindle acceleration" in desc
    evidence_list = []

    if has_spindle_noise or has_rapid_movement:
        evidence_list.append(Evidence(value=report.description))

    for event in events:
        if event.readings:
            for k, v in event.readings.items():
                val_str = str(v).lower()
                if "rapid movement" in val_str or "spindle acceleration" in val_str:
                    has_rapid_movement = True
                    evidence_list.append(Evidence(event_index=event.event_index, reading_key=k, value=v))  # type: ignore[arg-type]

    if has_spindle_noise and has_rapid_movement:
        return RuleResult(
            rule_id="spindle_inspection",
            status=RuleStatus.WARN,
            message="Inspection required before return to production",
            reason="Reported spindle noise during rapid movement matches the configured inspection rule.",
            evidence=evidence_list,
            severity=1,
        )

    return RuleResult(
        rule_id="spindle_inspection",
        status=RuleStatus.OK,
        message="Normal",
        reason="No spindle noise during rapid movement detected.",
        evidence=[],
        severity=0,
    )


def evaluate_coolant_condition(report: IssueReport, events: list[ReportEvent]) -> RuleResult:
    """
    Coolant Condition Rule:
    Expected coolant temperature: 18-24 °C.
    """
    evidence_list = []
    has_coolant = False

    for event in events:
        if event.readings and "coolant_temperature" in event.readings:
            has_coolant = True
            temp_val = event.readings["coolant_temperature"]
            evidence_list.append(Evidence(event_index=event.event_index, reading_key="coolant_temperature", value=temp_val))  # type: ignore[arg-type]

    if not has_coolant:
        return RuleResult(
            rule_id="coolant_condition",
            status=RuleStatus.MISSING,
            message="Coolant temperature reading missing",
            reason="No coolant temperature found in report events.",
            evidence=[],
            severity=0,
        )

    for ev in evidence_list:
        try:
            temp = float(ev.value)
        except (ValueError, TypeError):
            return RuleResult(
                rule_id="coolant_condition",
                status=RuleStatus.CONFLICT,
                message="Invalid coolant temperature reading",
                reason=f"Coolant temperature reading '{ev.value}' is not a valid number.",
                evidence=[ev],
                severity=2,  # Invalid reading raises a high severity equivalent
            )

        if temp < 18 or temp > 24:
            return RuleResult(
                rule_id="coolant_condition",
                status=RuleStatus.WARN,
                message="Coolant temperature out of range",
                reason=f"Current reading {temp} °C is outside the expected range of 18-24 °C.",
                evidence=[ev],
                severity=1,
            )

    return RuleResult(
        rule_id="coolant_condition",
        status=RuleStatus.OK,
        message="Coolant temperature normal",
        reason="Current reading is within the expected range of 18-24 °C.",
        evidence=evidence_list,
        severity=0,
    )


def evaluate_rules(report: IssueReport, events: list[ReportEvent]) -> list[RuleResult]:
    """
    Evaluate all deterministic rules against a report and its events.
    """
    return [
        evaluate_spindle_inspection(report, events),
        evaluate_coolant_condition(report, events),
    ]
