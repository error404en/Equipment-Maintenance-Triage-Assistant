import json

from app.ai import AIStatus, generate_ai_suggestions


class FakeLLM:
    def __init__(self, response_text: str, fail_with: Exception | None = None) -> None:
        self.response_text = response_text
        self.fail_with = fail_with

    def generate_json(self, prompt: str) -> str:
        if self.fail_with:
            raise self.fail_with
        return self.response_text


def test_valid_ai_response() -> None:
    valid_json = json.dumps({
        "findings": [
            {
                "kind": "observation",
                "description": "Observed spindle noise.",
                "citations": [{"chunk_id": "cnc-spindle"}]
            },
            {
                "kind": "possible_cause",
                "description": "Bearing wear.",
                "citations": [{"event_index": 1}]
            }
        ],
        "proposed_priority": 1
    })
    
    provider = FakeLLM(response_text=valid_json)
    result = generate_ai_suggestions(
        provider,
        prompt="...",
        retrieved_chunk_ids={"cnc-spindle"},
        supplied_event_indices={1, 2},
    )
    
    assert result.status == AIStatus.OK
    assert result.error_code is None
    assert result.response is not None
    assert len(result.response.findings) == 2
    assert result.response.proposed_priority == 1


def test_markdown_wrapper_is_stripped() -> None:
    valid_json = """```json
{
    "findings": [],
    "proposed_priority": 0
}
```"""
    provider = FakeLLM(response_text=valid_json)
    result = generate_ai_suggestions(
        provider,
        prompt="...",
        retrieved_chunk_ids=set(),
        supplied_event_indices=set(),
    )
    
    assert result.status == AIStatus.OK


def test_schema_violation_extra_fields() -> None:
    # LLM hallucinates a "diagnosis" field which is strictly forbidden
    invalid_json = json.dumps({
        "findings": [],
        "proposed_priority": 1,
        "diagnosis": "spindle failure"
    })
    provider = FakeLLM(response_text=invalid_json)
    result = generate_ai_suggestions(
        provider,
        prompt="...",
        retrieved_chunk_ids=set(),
        supplied_event_indices=set(),
    )
    
    assert result.status == AIStatus.DEGRADED
    assert result.error_code == "SCHEMA_VIOLATION"


def test_schema_violation_invalid_finding_kind() -> None:
    invalid_json = json.dumps({
        "findings": [
            {
                "kind": "confirmed",  # Not allowed by AI
                "description": "Test",
                "citations": [{"event_index": 1}]
            }
        ],
        "proposed_priority": 1
    })
    provider = FakeLLM(response_text=invalid_json)
    result = generate_ai_suggestions(
        provider,
        prompt="...",
        retrieved_chunk_ids=set(),
        supplied_event_indices={1},
    )
    
    assert result.status == AIStatus.DEGRADED
    assert result.error_code == "SCHEMA_VIOLATION"


def test_schema_violation_citation_structure() -> None:
    # A citation must have EXACTLY ONE of chunk_id or event_index
    invalid_json_both = json.dumps({
        "findings": [
            {
                "kind": "observation",
                "description": "Test",
                "citations": [{"chunk_id": "chunk-1", "event_index": 1}]
            }
        ],
        "proposed_priority": 1
    })
    provider = FakeLLM(response_text=invalid_json_both)
    result = generate_ai_suggestions(
        provider,
        prompt="...",
        retrieved_chunk_ids={"chunk-1"},
        supplied_event_indices={1},
    )
    assert result.status == AIStatus.DEGRADED
    assert result.error_code == "SCHEMA_VIOLATION"

    invalid_json_neither = json.dumps({
        "findings": [
            {
                "kind": "observation",
                "description": "Test",
                "citations": [{}]
            }
        ],
        "proposed_priority": 1
    })
    provider2 = FakeLLM(response_text=invalid_json_neither)
    result2 = generate_ai_suggestions(
        provider2,
        prompt="...",
        retrieved_chunk_ids=set(),
        supplied_event_indices=set(),
    )
    assert result2.status == AIStatus.DEGRADED
    assert result2.error_code == "SCHEMA_VIOLATION"


def test_citation_validation_missing_citations() -> None:
    # Findings must have at least one citation
    invalid_json = json.dumps({
        "findings": [
            {
                "kind": "observation",
                "description": "Test",
                "citations": []
            }
        ],
        "proposed_priority": 1
    })
    provider = FakeLLM(response_text=invalid_json)
    result = generate_ai_suggestions(
        provider,
        prompt="...",
        retrieved_chunk_ids=set(),
        supplied_event_indices=set(),
    )
    assert result.status == AIStatus.DEGRADED
    assert result.error_code == "CITATION_VALIDATION_FAILED"


def test_citation_validation_invalid_chunk_id() -> None:
    valid_json = json.dumps({
        "findings": [
            {
                "kind": "observation",
                "description": "Test",
                "citations": [{"chunk_id": "hallucinated-chunk"}]
            }
        ],
        "proposed_priority": 1
    })
    provider = FakeLLM(response_text=valid_json)
    result = generate_ai_suggestions(
        provider,
        prompt="...",
        # Chunk exists in real KB maybe, but wasn't retrieved for THIS query
        retrieved_chunk_ids={"actual-chunk-1"},
        supplied_event_indices=set(),
    )
    assert result.status == AIStatus.DEGRADED
    assert result.error_code == "CITATION_VALIDATION_FAILED"


def test_citation_validation_invalid_event_index() -> None:
    valid_json = json.dumps({
        "findings": [
            {
                "kind": "observation",
                "description": "Test",
                "citations": [{"event_index": 999}]
            }
        ],
        "proposed_priority": 1
    })
    provider = FakeLLM(response_text=valid_json)
    result = generate_ai_suggestions(
        provider,
        prompt="...",
        retrieved_chunk_ids=set(),
        supplied_event_indices={1, 2},  # 999 not provided
    )
    assert result.status == AIStatus.DEGRADED
    assert result.error_code == "CITATION_VALIDATION_FAILED"


def test_malformed_json_handled() -> None:
    provider = FakeLLM(response_text="This is just plain text, not JSON.")
    result = generate_ai_suggestions(
        provider,
        prompt="...",
        retrieved_chunk_ids=set(),
        supplied_event_indices=set(),
    )
    assert result.status == AIStatus.DEGRADED
    assert result.error_code == "JSON_PARSE_ERROR"


def test_provider_exception_handled() -> None:
    provider = FakeLLM(response_text="", fail_with=TimeoutError("API Down"))
    result = generate_ai_suggestions(
        provider,
        prompt="...",
        retrieved_chunk_ids=set(),
        supplied_event_indices=set(),
    )
    assert result.status == AIStatus.UNAVAILABLE
    assert result.error_code == "PROVIDER_ERROR"
