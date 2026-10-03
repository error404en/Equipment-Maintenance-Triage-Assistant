import json
from enum import Enum
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str | None = None
    event_index: int | None = None

    @model_validator(mode="after")
    def check_exactly_one_field(self) -> "Citation":
        has_chunk = self.chunk_id is not None
        has_event = self.event_index is not None
        if has_chunk == has_event:
            raise ValueError("Citation must contain exactly one of 'chunk_id' or 'event_index'")
        return self


class AICitedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str
    citations: list[Citation]

class AIFinding(AICitedItem):
    kind: Literal["observation", "possible_cause"]

class AIResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[AIFinding]
    follow_up_questions: list[AICitedItem]
    inspection_steps: list[AICitedItem]
    priority_reason: AICitedItem
    proposed_priority: Literal[0, 1, 2]


class AIStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class AIResult(BaseModel):
    status: AIStatus
    error_code: str | None = None
    response: AIResponse | None = None
    raw_output: str | None = None


class LLMProvider(Protocol):
    model: str
    def generate_json(self, prompt: str) -> str:
        """Synchronously generates a JSON string response from the LLM."""
        ...


class GroqLLMProvider:
    def __init__(self, api_key: str, model: str) -> None:
        import groq
        self.client = groq.Groq(api_key=api_key)
        self.model = model

    def generate_json(self, prompt: str) -> str:
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an industrial equipment diagnostic assistant. "
                            "You MUST respond ONLY with valid JSON matching this schema: "
                            "{'findings': [{'kind': 'observation'|'possible_cause', 'description': str, 'citations': [{'chunk_id': str} | {'event_index': int}]}], "
                            "'follow_up_questions': [{'description': str, 'citations': ...}], "
                            "'inspection_steps': [{'description': str, 'citations': ...}], "
                            "'priority_reason': {'description': str, 'citations': ...}, "
                            "'proposed_priority': 0|1|2}. "
                            "Do not output markdown formatting like ```json, just the raw JSON object. "
                            "Never output 'confirmed' findings. EVERY item (findings, questions, steps, priority_reason) MUST carry citations."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
                timeout=30.0,
            )
        except Exception as e:
            if "timeout" in str(e).lower():
                raise TimeoutError(str(e))
            raise
        return completion.choices[0].message.content or ""


class CitationValidationError(Exception):
    pass


def strip_markdown(text: str) -> str:
    text = text.strip()
    if text.startswith("```json\n") and text.endswith("\n```"):
        return text[8:-4].strip()
    elif text.startswith("```json") and text.endswith("```"):
        return text[7:-3].strip()
    return text


def validate_citations(
    response: AIResponse,
    retrieved_chunk_ids: set[str],
    supplied_event_indices: set[int],
) -> None:
    all_items: list[AICitedItem] = []
    all_items.extend(response.findings)
    all_items.extend(response.follow_up_questions)
    all_items.extend(response.inspection_steps)
    all_items.append(response.priority_reason)

    for item in all_items:
        if not item.citations:
            raise CitationValidationError("Item has no citations.")
        for citation in item.citations:
            if citation.chunk_id is not None:
                if citation.chunk_id not in retrieved_chunk_ids:
                    raise CitationValidationError(
                        f"Citation chunk_id '{citation.chunk_id}' not in retrieved chunks."
                    )
            elif citation.event_index is not None and citation.event_index not in supplied_event_indices:
                raise CitationValidationError(
                    f"Citation event_index '{citation.event_index}' not in supplied events."
                )


def generate_ai_suggestions(
    provider: LLMProvider,
    prompt: str,
    retrieved_chunk_ids: set[str],
    supplied_event_indices: set[int],
) -> AIResult:
    try:
        raw_output = provider.generate_json(prompt)
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f"Provider error: {e}")
        # Any provider-level exception constitutes UNAVAILABLE
        return AIResult(status=AIStatus.UNAVAILABLE, error_code="PROVIDER_ERROR")

    cleaned_json = strip_markdown(raw_output)

    try:
        data = json.loads(cleaned_json)
    except json.JSONDecodeError:
        return AIResult(status=AIStatus.DEGRADED, error_code="JSON_PARSE_ERROR", raw_output=raw_output)

    try:
        response = AIResponse.model_validate(data)
    except ValidationError:
        return AIResult(status=AIStatus.DEGRADED, error_code="SCHEMA_VIOLATION", raw_output=raw_output)

    try:
        validate_citations(response, retrieved_chunk_ids, supplied_event_indices)
    except CitationValidationError:
        return AIResult(status=AIStatus.DEGRADED, error_code="CITATION_VALIDATION_FAILED", raw_output=raw_output)

    return AIResult(status=AIStatus.OK, response=response, raw_output=raw_output)
