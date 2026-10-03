import json

from app.ai import AIResult, AIStatus, LLMProvider, generate_ai_suggestions
from app.models import IssueReport, ReportEvent
from app.retrieval import Retriever
from app.rules import evaluate_rules
from app.schemas import AnalysisResponse


def run_analysis(
    report: IssueReport,
    events: list[ReportEvent],
    retriever: Retriever,
    provider: LLMProvider | None = None,
) -> AnalysisResponse:
    # 1. Deterministic Rule Execution
    rule_results = evaluate_rules(report, events)
    rule_max_severity = max((r.severity for r in rule_results), default=0)

    # 2. Knowledge Retrieval
    equipment_type = str(report.equipment.type) if report.equipment else None
    query = str(report.description) if report.description else ""
    retrieved_chunks = retriever.search(query=query, equipment_type=equipment_type)

    valid_chunk_ids = {str(c.chunk_id) for c in retrieved_chunks}
    valid_event_indices = {int(e.event_index) for e in events}

    # 3. AI Execution (Guarded Boundary)
    if not provider:
        # Fast path exit if no provider is configured (e.g. default/production without paid API)
        ai_result = AIResult(
            status=AIStatus.UNAVAILABLE,
            error_code="NO_PROVIDER_CONFIGURED",
        )
    else:
        # Format the prompt
        # Explicitly instruct the LLM not to contradict the deterministic rules.
        rule_summaries = [f"- {r.rule_id}: {r.status.value} (Severity {r.severity})" for r in rule_results]
        chunk_summaries = [f"Chunk ID: {c.chunk_id}\n{c.content}" for c in retrieved_chunks]
        event_summaries = [f"Event {e.event_index}: {json.dumps(e.readings)}" for e in events]

        prompt = (
            "Analyze the following equipment issue report.\n"
            "IMPORTANT: Do not duplicate or override the following deterministic rule results. "
            "They are authoritative. Provide only complementary observations and possible causes.\n\n"
            f"Description: {report.description}\n\n"
            "Events:\n" + "\n".join(event_summaries) + "\n\n"
            "Deterministic Rule Results:\n" + "\n".join(rule_summaries) + "\n\n"
            "Knowledge Base Chunks:\n" + "\n\n".join(chunk_summaries) + "\n"
        )
        ai_result = generate_ai_suggestions(
            provider=provider,
            prompt=prompt,
            retrieved_chunk_ids=valid_chunk_ids,
            supplied_event_indices=valid_event_indices,
        )

    # 4. Merge results and calculate final priority
    ai_priority = 0
    ai_findings = []

    if ai_result.status == AIStatus.OK and ai_result.response:
        ai_priority = ai_result.response.proposed_priority
        ai_findings = ai_result.response.findings

    final_priority = max(rule_max_severity, ai_priority)

    return AnalysisResponse(
        report_id=int(report.id),
        equipment_id=int(report.equipment_id),
        rule_results=rule_results,
        ai_status=ai_result.status,
        ai_error_code=ai_result.error_code,
        ai_findings=ai_findings,
        final_priority=final_priority,
    )
