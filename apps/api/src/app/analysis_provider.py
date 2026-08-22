import json
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings
from app.transcripts import TranscriptTurn


class AnalysisProviderError(RuntimeError):
    """Raised when the configured local analysis provider cannot answer safely."""


class AnalysisProvider(Protocol):
    def generate(self, turns: list[TranscriptTurn]) -> "GeneratedAnalysis": ...


@dataclass(frozen=True)
class GeneratedAnalysis:
    raw_output: str
    model_version: str


class OllamaAnalysisProvider:
    """Generate structured call analysis using an Ollama model running on this device."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model
        self._timeout_seconds = settings.analysis_timeout_seconds

    def generate(self, turns: list[TranscriptTurn]) -> GeneratedAnalysis:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": _transcript_payload(turns)},
            ],
            "format": _output_schema(),
            "stream": False,
            "options": {"temperature": 0},
        }
        request = Request(
            f"{self._base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise AnalysisProviderError("local_model_unavailable") from error

        content = response_payload.get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise AnalysisProviderError("local_model_invalid_response")
        response_model = response_payload.get("model", self._model)
        if not isinstance(response_model, str):
            response_model = self._model
        return GeneratedAnalysis(raw_output=content, model_version=f"ollama:{response_model}")


def _system_prompt() -> str:
    return (
        "You analyze customer-service call transcripts for a manager. Return only JSON matching "
        "the requested schema. Use only the supplied transcript. Overall mood means the customer's "
        "evidenced attitude in their words, never voice tone. Default to neutral when the customer "
        "does not clearly express sentiment. Do not classify an agent greeting, offer of help, "
        "apology, "
        "or routine support wording as customer negativity. A mood shift is allowed only when the "
        "customer's own words clearly show a change; otherwise return an empty mood_shifts array. "
        "For every claim and mood shift, copy transcript_turn_id, quote, start_ms, and end_ms "
        "exactly "
        "from one supplied turn. Do not invent evidence. Keep summary to 40 words or fewer. "
        "Recommended action is advice, not evidence."
    )


def _transcript_payload(turns: list[TranscriptTurn]) -> str:
    return json.dumps(
        {
            "turns": [
                {
                    "transcript_turn_id": turn.transcript_turn_id,
                    "speaker": turn.speaker,
                    "start_ms": turn.start_ms,
                    "end_ms": turn.end_ms,
                    "text": turn.text,
                }
                for turn in turns
            ]
        },
        ensure_ascii=True,
    )


def _output_schema() -> dict[str, object]:
    properties = {
        "intent": {"type": "string"},
        "mood": {"type": "string", "enum": ["positive", "neutral", "negative", "mixed"]},
        "resolution": {"type": "string", "enum": ["resolved", "unresolved", "unclear"]},
        "summary": {"type": "string"},
        "manager_brief": {"type": "string"},
        "recommended_action": {"type": "string"},
        "claims": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": _evidence_properties("claim"),
                "required": ["claim", "transcript_turn_id", "quote", "start_ms", "end_ms"],
                "additionalProperties": False,
            },
        },
        "mood_shifts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    **_evidence_properties("reason"),
                    "from_mood": {
                        "type": "string",
                        "enum": ["positive", "neutral", "negative", "mixed"],
                    },
                    "to_mood": {
                        "type": "string",
                        "enum": ["positive", "neutral", "negative", "mixed"],
                    },
                },
                "required": [
                    "from_mood",
                    "to_mood",
                    "reason",
                    "transcript_turn_id",
                    "quote",
                    "start_ms",
                    "end_ms",
                ],
                "additionalProperties": False,
            },
        },
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _evidence_properties(label: str) -> dict[str, object]:
    return {
        label: {"type": "string"},
        "transcript_turn_id": {"type": "string"},
        "quote": {"type": "string"},
        "start_ms": {"type": "integer"},
        "end_ms": {"type": "integer"},
    }
