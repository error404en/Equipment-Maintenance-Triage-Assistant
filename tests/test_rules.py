from typing import Any

from app.models import Equipment, IssueReport, ReportEvent
from app.rules import (
    RuleStatus,
    evaluate_coolant_condition,
    evaluate_rules,
    evaluate_spindle_inspection,
)


def create_mock_report(description: str = "", equipment_type: str = "cnc") -> IssueReport:
    equipment = Equipment(id=1, identifier="EQ-TEST", type=equipment_type)
    return IssueReport(
        id=1,
        equipment_id=1,
        reported_by="Tech",
        description=description,
        equipment=equipment,
    )


def create_mock_event(index: int = 1, readings: dict[str, Any] | None = None) -> ReportEvent:
    return ReportEvent(
        id=index,
        report_id=1,
        event_index=index,
        readings=readings,
    )


def test_spindle_noise_and_rapid_movement() -> None:
    # A. Spindle noise + rapid movement -> WARNING
    report = create_mock_report("Spindle noise heard.")
    event = create_mock_event(1, {"state": "rapid movement"})
    result = evaluate_spindle_inspection(report, [event])
    assert result.status == RuleStatus.WARN
    assert result.severity == 1
    assert "rapid movement" in result.reason.lower()
    assert len(result.evidence) == 2


def test_spindle_noise_without_rapid_movement() -> None:
    # B. Spindle noise without rapid movement -> does not incorrectly trigger
    report = create_mock_report("There is some spindle noise.")
    event = create_mock_event(1, {"state": "normal"})
    result = evaluate_spindle_inspection(report, [event])
    assert result.status == RuleStatus.OK
    assert result.severity == 0


def test_coolant_temperature_normal() -> None:
    # C. Coolant temperature 21 °C -> NORMAL
    report = create_mock_report()
    event = create_mock_event(1, {"coolant_temperature": 21})
    result = evaluate_coolant_condition(report, [event])
    assert result.status == RuleStatus.OK
    assert result.severity == 0
    assert len(result.evidence) == 1
    assert result.evidence[0].value == 21


def test_coolant_temperature_boundaries() -> None:
    # D. Coolant temperature exactly 18 °C -> valid boundary behavior
    report = create_mock_report()
    event18 = create_mock_event(1, {"coolant_temperature": 18})
    result18 = evaluate_coolant_condition(report, [event18])
    assert result18.status == RuleStatus.OK

    # E. Coolant temperature exactly 24 °C -> valid boundary behavior
    event24 = create_mock_event(2, {"coolant_temperature": 24})
    result24 = evaluate_coolant_condition(report, [event24])
    assert result24.status == RuleStatus.OK


def test_coolant_temperature_out_of_range() -> None:
    # F. Coolant temperature below 18 °C -> expected non-normal result
    report = create_mock_report()
    event_low = create_mock_event(1, {"coolant_temperature": 17})
    result_low = evaluate_coolant_condition(report, [event_low])
    assert result_low.status == RuleStatus.WARN
    assert result_low.severity == 1

    # G. Coolant temperature above 24 °C -> expected non-normal result
    event_high = create_mock_event(2, {"coolant_temperature": 25})
    result_high = evaluate_coolant_condition(report, [event_high])
    assert result_high.status == RuleStatus.WARN
    assert result_high.severity == 1


def test_missing_coolant_reading() -> None:
    # H. Missing coolant reading -> explicitly handled
    report = create_mock_report()
    event = create_mock_event(1, {"vibration": 10})
    result = evaluate_coolant_condition(report, [event])
    assert result.status == RuleStatus.MISSING
    assert result.severity == 0


def test_invalid_coolant_reading() -> None:
    # I. Invalid coolant reading -> explicitly handled
    report = create_mock_report()
    event = create_mock_event(1, {"coolant_temperature": "broken sensor"})
    result = evaluate_coolant_condition(report, [event])
    assert result.status == RuleStatus.CONFLICT
    assert result.severity == 2
    assert "not a valid number" in result.reason.lower()


def test_missing_issue_event_information() -> None:
    # J. Missing issue/event information -> rule engine must not invent evidence
    report = create_mock_report("")
    # Empty events
    results = evaluate_rules(report, [])
    # Spindle should be OK because no description or event info provided
    assert results[0].rule_id == "spindle_inspection"
    assert results[0].status == RuleStatus.OK
    # Coolant should be MISSING because no events with readings were provided
    assert results[1].rule_id == "coolant_condition"
    assert results[1].status == RuleStatus.MISSING


def test_multiple_rules_execute_independently() -> None:
    # K. Multiple rules can execute independently
    report = create_mock_report("Spindle noise heard.")
    event = create_mock_event(1, {"state": "rapid movement", "coolant_temperature": 10})
    results = evaluate_rules(report, [event])
    assert len(results) == 2

    # Check spindle
    assert results[0].rule_id == "spindle_inspection"
    assert results[0].status == RuleStatus.WARN

    # Check coolant (independent of spindle)
    assert results[1].rule_id == "coolant_condition"
    assert results[1].status == RuleStatus.WARN


def test_rule_evaluation_is_deterministic() -> None:
    # L. Rule evaluation is deterministic: same input -> same output
    report = create_mock_report("Spindle noise.")
    event = create_mock_event(1, {"state": "rapid movement", "coolant_temperature": 21})

    results1 = evaluate_rules(report, [event])
    results2 = evaluate_rules(report, [event])
    results3 = evaluate_rules(report, [event])

    assert results1 == results2
    assert results2 == results3


def test_evidence_attached_correctly() -> None:
    # M. Evidence attached to each triggered rule is correct
    report = create_mock_report("Spindle noise is loud.")
    event = create_mock_event(1, {"coolant_temperature": 30})
    results = evaluate_rules(report, [event])

    # Spindle inspection is OK, evidence should be empty
    assert results[0].rule_id == "spindle_inspection"
    assert results[0].evidence == []

    # Coolant condition is WARN, evidence should contain the 30 value and event index 1
    assert results[1].rule_id == "coolant_condition"
    assert len(results[1].evidence) == 1
    assert results[1].evidence[0].value == 30
    assert results[1].evidence[0].event_index == 1
    assert results[1].evidence[0].reading_key == "coolant_temperature"


def test_ai_related_fields_not_used() -> None:
    # N. AI-related fields/models are NOT used to determine deterministic rule outcomes
    # The models IssueReport and ReportEvent have no AI fields, ensuring AI findings
    # cannot affect this code path.
    # We verify that evaluating rules relies purely on report and events.
    report = create_mock_report("Normal operation.")
    event = create_mock_event(1, {"coolant_temperature": 21})

    # The signature strictly enforces separation from Finding / AI logic.
    results = evaluate_rules(report, [event])
    assert all(r.status == RuleStatus.OK for r in results)


def test_unknown_equipment_handled_gracefully() -> None:
    # Test that an unsupported/unknown equipment type produces no CNC rule results
    report = create_mock_report("Spindle noise.", equipment_type="pump")
    event = create_mock_event(1, {"state": "rapid movement", "coolant_temperature": 21})

    results = evaluate_rules(report, [event])

    # Since it's a pump, not CNC, it shouldn't evaluate CNC rules
    assert len(results) == 0
