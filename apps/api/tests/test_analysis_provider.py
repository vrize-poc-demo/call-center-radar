import json

import pytest

from app.analysis_provider import AnalysisProviderError, GeneratedAnalysis, OllamaAnalysisProvider
from app.config import Settings
from app.transcripts import TranscriptTurn


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_ollama_provider_sends_local_structured_request(monkeypatch, tmp_path) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _Response({"model": "qwen2.5:7b", "message": {"content": "{}"}})

    monkeypatch.setattr("app.analysis_provider.urlopen", fake_urlopen)
    provider = OllamaAnalysisProvider(
        Settings(database_path=tmp_path / "calls.db", sample_data_dir=tmp_path / "samples")
    )

    generated = provider.generate(
        [
            TranscriptTurn(
                transcript_turn_id="turn-1",
                speaker="customer",
                start_ms=0,
                end_ms=1000,
                text="Please review my account.",
            )
        ]
    )

    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    assert captured["timeout"] == 90.0
    assert captured["payload"]["model"] == "qwen2.5:7b"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["options"] == {"temperature": 0}
    assert captured["payload"]["format"]["properties"]["claims"]["minItems"] == 1
    assert captured["payload"]["format"]["required"] == [
        "intent",
        "mood",
        "resolution",
        "summary",
        "manager_brief",
        "recommended_action",
        "claims",
        "mood_shifts",
    ]
    assert "agent greeting" in captured["payload"]["messages"][0]["content"]
    turn_id = json.loads(captured["payload"]["messages"][1]["content"])["turns"][0][
        "transcript_turn_id"
    ]
    assert turn_id == "turn-1"
    assert generated == GeneratedAnalysis(raw_output="{}", model_version="ollama:qwen2.5:7b")


def test_ollama_provider_rejects_an_empty_local_response(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.analysis_provider.urlopen",
        lambda request, timeout: _Response({"model": "qwen2.5:7b", "message": {"content": ""}}),
    )
    provider = OllamaAnalysisProvider(
        Settings(database_path=tmp_path / "calls.db", sample_data_dir=tmp_path / "samples")
    )

    with pytest.raises(AnalysisProviderError, match="local_model_invalid_response"):
        provider.generate([])
