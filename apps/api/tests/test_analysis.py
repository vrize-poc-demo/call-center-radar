import json

import pytest
from fastapi.testclient import TestClient

from app.analysis import parse_model_output
from app.analysis_provider import AnalysisProviderError, GeneratedAnalysis
from app.config import Settings
from app.main import create_app
from app.summary import MAX_SUMMARY_WORDS
from app.transcripts import TranscriptTurn


class FixtureAnalysisProvider:
    """A deterministic provider double; production uses only local Ollama."""

    def generate(self, turns: list[TranscriptTurn]) -> GeneratedAnalysis:
        first = turns[0]
        mood_shifts = []
        mood = "negative"
        if len(turns) > 1:
            recovery = turns[-1]
            mood = "positive"
            mood_shifts = [
                _mood_shift("neutral", "negative", first),
                _mood_shift("negative", "positive", recovery),
            ]
        return GeneratedAnalysis(
            raw_output=json.dumps(
                {
                    "intent": "Support request",
                    "mood": mood,
                    "resolution": "unresolved",
                    "summary": "The customer requested support.",
                    "manager_brief": "Review the customer request.",
                    "recommended_action": "Confirm the next owner.",
                    "claims": [_claim(first)],
                    "mood_shifts": mood_shifts,
                }
            ),
            model_version="fixture:test-v1",
        )


class InvalidOptionalMoodShiftProvider:
    def generate(self, turns: list[TranscriptTurn]) -> GeneratedAnalysis:
        first = turns[0]
        return GeneratedAnalysis(
            raw_output=json.dumps(
                {
                    "intent": "Support request",
                    "mood": "negative",
                    "resolution": "unclear",
                    "summary": "The customer requested support.",
                    "manager_brief": "Review the customer request.",
                    "recommended_action": "Confirm the next owner.",
                    "claims": [_claim(first)],
                    "mood_shifts": [
                        {
                            "from_mood": "neutral",
                            "to_mood": "negative",
                            "reason": "Unsupported model quote.",
                            "transcript_turn_id": "unknown-turn",
                            "quote": "This text was never saved.",
                            "start_ms": first.start_ms,
                            "end_ms": first.end_ms,
                        }
                    ],
                }
            ),
            model_version="fixture:invalid-optional-shift",
        )


def _claim(turn: TranscriptTurn) -> dict[str, object]:
    return {
        "claim": "Customer support concern",
        "transcript_turn_id": turn.transcript_turn_id,
        "quote": turn.text,
        "start_ms": turn.start_ms,
        "end_ms": turn.end_ms,
    }


def _mood_shift(from_mood: str, to_mood: str, turn: TranscriptTurn) -> dict[str, object]:
    return {
        "from_mood": from_mood,
        "to_mood": to_mood,
        "reason": "Fixture evidence-backed change.",
        "transcript_turn_id": turn.transcript_turn_id,
        "quote": turn.text,
        "start_ms": turn.start_ms,
        "end_ms": turn.end_ms,
    }


def create_test_app(settings: Settings):
    app = create_app(settings)
    app.state.analysis_provider = FixtureAnalysisProvider()
    return app


def test_parses_structured_analysis_output() -> None:
    analysis = parse_model_output(
        '{"intent":"Support","mood":"negative","resolution":"unresolved",'
        '"summary":"A summary","manager_brief":"A brief",'
        '"recommended_action":"Follow up","claims":[{"claim":"Support request",'
        '"transcript_turn_id":"turn-1","quote":"Need help","start_ms":0,"end_ms":1000}],'
        '"mood_shifts":['
        '{"from_mood":"neutral","to_mood":"negative","reason":"Issue raised",'
        '"transcript_turn_id":"turn-1","quote":"Need help","start_ms":0,'
        '"end_ms":1000}]}',
        "test-v1",
    )

    assert analysis.resolution == "unresolved"
    assert analysis.model_version == "test-v1"
    assert analysis.mood_shifts[0].to_mood == "negative"


def test_rejects_malformed_structured_analysis_output() -> None:
    with pytest.raises(ValueError):
        parse_model_output('{"intent":"Support"}', "test-v1")


def test_rejects_analysis_without_evidence_claims() -> None:
    with pytest.raises(ValueError):
        parse_model_output(
            '{"intent":"Support","mood":"neutral","resolution":"unclear",'
            '"summary":"Summary","manager_brief":"Brief",'
            '"recommended_action":"Follow up","claims":[],"mood_shifts":[]}',
            "test-v1",
        )


def test_normalizes_a_summary_before_exposing_it() -> None:
    analysis = parse_model_output(
        '{"intent":"Support","mood":"neutral","resolution":"unclear",'
        '"summary":"  Card,   replacement\\narrives tomorrow.  ",'
        '"manager_brief":"Brief","recommended_action":"Follow up",'
        '"claims":[{"claim":"Support request","transcript_turn_id":"turn-1",'
        '"quote":"Need help","start_ms":0,"end_ms":1000}],"mood_shifts":[]}',
        "test-v1",
    )

    assert analysis.summary == "Card, replacement arrives tomorrow."


def test_rejects_a_model_summary_above_forty_words() -> None:
    with pytest.raises(ValueError, match="summary_word_limit_exceeded"):
        parse_model_output(
            json.dumps(
                {
                    "intent": "Support",
                    "mood": "neutral",
                    "resolution": "unclear",
                    "summary": "word " * (MAX_SUMMARY_WORDS + 1),
                    "manager_brief": "Brief",
                    "recommended_action": "Follow up",
                    "claims": [
                        {
                            "claim": "Support request",
                            "transcript_turn_id": "turn-1",
                            "quote": "Need help",
                            "start_ms": 0,
                            "end_ms": 1000,
                        }
                    ],
                    "mood_shifts": [],
                }
            ),
            "test-v1",
        )


def test_analyzes_five_calls_with_evidence_backed_claims(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "calls.db",
        sample_data_dir=tmp_path / "samples",
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=1024,
    )
    call_texts = [
        "I need help with this account issue.",
        "This error is still not working.",
        "Please help me resolve the problem.",
        "I cannot access my service.",
        "There is an issue with my payment.",
    ]

    with TestClient(create_test_app(settings)) as client:
        for index, text in enumerate(call_texts):
            call_id = client.post(
                "/api/calls",
                data={"agent_name": "Demo Agent", "customer_name": f"Customer {index}"},
                files={"audio": (f"call-{index}.wav", b"audio", "audio/wav")},
            ).json()["call_id"]
            saved = client.put(
                f"/api/calls/{call_id}/transcript",
                json={
                    "turns": [
                        {
                            "speaker": "customer",
                            "start_ms": 0,
                            "end_ms": 1000,
                            "text": text,
                        }
                    ]
                },
            ).json()
            response = client.get(f"/api/calls/{call_id}/analysis")

            assert response.status_code == 200
            claim = response.json()["analysis"]["claims"][0]
            assert claim["transcript_turn_id"] == saved["turns"][0]["transcript_turn_id"]
            assert claim["quote"] == text
            assert claim["start_ms"] == 0
            assert claim["end_ms"] == 1000
            assert response.json()["analysis"]["mood_shifts"] == []
            assert response.json()["analysis"]["false_resolution"] is None


def test_analysis_is_persisted_refreshed_and_exposed_for_dashboard_triage(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "calls.db",
        sample_data_dir=tmp_path / "samples",
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=1024,
    )
    with TestClient(create_test_app(settings)) as client:
        call_id = client.post(
            "/api/calls",
            data={"agent_name": "Agent", "customer_name": "Customer"},
            files={"audio": ("call.wav", b"audio", "audio/wav")},
        ).json()["call_id"]
        saved = client.put(
            f"/api/calls/{call_id}/transcript",
            json={
                "turns": [
                    {
                        "speaker": "customer",
                        "start_ms": 100,
                        "end_ms": 900,
                        "text": "This issue is still not working.",
                    }
                ]
            },
        ).json()

        first = client.get(f"/api/calls/{call_id}/analysis")
        cached = client.get(f"/api/calls/{call_id}/analysis")
        refreshed = client.post(f"/api/calls/{call_id}/analysis")
        priority = client.post(f"/api/calls/{call_id}/priority")
        triage = client.get("/api/dashboard/triage")

    assert first.status_code == 200
    assert cached.status_code == 200
    assert first.json()["analysis"] == cached.json()["analysis"]
    assert first.json()["analysis"]["analysis_version"] == 1
    assert refreshed.status_code == 200
    assert refreshed.json()["analysis"]["analysis_version"] == 2
    assert priority.status_code == 200
    assert triage.status_code == 200
    item = triage.json()["calls"][0]
    assert item["call_id"] == call_id
    assert item["analysis"]["analysis_version"] == 2
    assert item["analysis"]["summary"] == "The customer requested support."
    assert item["analysis"]["mood"] == "negative"
    assert item["radar_priority"] == 100
    assert item["risk_level"] == "high"
    assert item["analysis"]["false_resolution"] is False
    assert "quote" not in item["analysis"]
    assert (
        first.json()["analysis"]["claims"][0]["transcript_turn_id"]
        == saved["turns"][0]["transcript_turn_id"]
    )


def test_persists_ordered_mood_shift_evidence(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "calls.db",
        sample_data_dir=tmp_path / "samples",
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=1024,
    )
    with TestClient(create_test_app(settings)) as client:
        call_id = client.post(
            "/api/calls",
            data={"agent_name": "Agent", "customer_name": "Customer"},
            files={"audio": ("call.wav", b"audio", "audio/wav")},
        ).json()["call_id"]
        saved = client.put(
            f"/api/calls/{call_id}/transcript",
            json={
                "turns": [
                    {
                        "speaker": "customer",
                        "start_ms": 0,
                        "end_ms": 1000,
                        "text": "This issue is not working.",
                    },
                    {
                        "speaker": "customer",
                        "start_ms": 1200,
                        "end_ms": 2000,
                        "text": "Thank you, it is working now.",
                    },
                ]
            },
        ).json()
        analysis = client.get(f"/api/calls/{call_id}/analysis").json()["analysis"]

    assert analysis["mood"] == "positive"
    assert [(shift["from_mood"], shift["to_mood"]) for shift in analysis["mood_shifts"]] == [
        ("neutral", "negative"),
        ("negative", "positive"),
    ]
    assert (
        analysis["mood_shifts"][1]["transcript_turn_id"] == saved["turns"][1]["transcript_turn_id"]
    )


def test_discards_invalid_optional_mood_shift_without_hiding_valid_analysis(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "calls.db",
        sample_data_dir=tmp_path / "samples",
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=1024,
    )
    app = create_app(settings)
    app.state.analysis_provider = InvalidOptionalMoodShiftProvider()
    with TestClient(app) as client:
        call_id = client.post(
            "/api/calls",
            data={"agent_name": "Agent", "customer_name": "Customer"},
            files={"audio": ("call.wav", b"audio", "audio/wav")},
        ).json()["call_id"]
        client.put(
            f"/api/calls/{call_id}/transcript",
            json={
                "turns": [
                    {
                        "speaker": "customer",
                        "start_ms": 0,
                        "end_ms": 1000,
                        "text": "I need help with my account.",
                    }
                ]
            },
        )
        response = client.get(f"/api/calls/{call_id}/analysis")

    assert response.status_code == 200
    assert response.json()["analysis"]["claims"][0]["quote"] == "I need help with my account."
    assert response.json()["analysis"]["mood_shifts"] == []


def test_derives_claim_quote_and_timing_from_known_saved_turn(tmp_path) -> None:
    class ShortenedQuoteProvider:
        def generate(self, turns: list[TranscriptTurn]) -> GeneratedAnalysis:
            first = turns[0]
            return GeneratedAnalysis(
                raw_output=json.dumps(
                    {
                        "intent": "Support request",
                        "mood": "neutral",
                        "resolution": "unclear",
                        "summary": "The customer requested support.",
                        "manager_brief": "Review the customer request.",
                        "recommended_action": "Confirm the next owner.",
                        "claims": [
                            {
                                **_claim(first),
                                "quote": "Need help",
                                "start_ms": 1,
                                "end_ms": 2,
                            }
                        ],
                        "mood_shifts": [],
                    }
                ),
                model_version="fixture:shortened-quote",
            )

    settings = Settings(
        database_path=tmp_path / "calls.db",
        sample_data_dir=tmp_path / "samples",
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=1024,
    )
    app = create_app(settings)
    app.state.analysis_provider = ShortenedQuoteProvider()
    with TestClient(app) as client:
        call_id = client.post(
            "/api/calls",
            data={"agent_name": "Agent", "customer_name": "Customer"},
            files={"audio": ("call.wav", b"audio", "audio/wav")},
        ).json()["call_id"]
        saved = client.put(
            f"/api/calls/{call_id}/transcript",
            json={
                "turns": [
                    {
                        "speaker": "customer",
                        "start_ms": 100,
                        "end_ms": 900,
                        "text": "I need help with my account.",
                    }
                ]
            },
        ).json()
        response = client.get(f"/api/calls/{call_id}/analysis")

    claim = response.json()["analysis"]["claims"][0]
    assert response.status_code == 200
    assert claim["transcript_turn_id"] == saved["turns"][0]["transcript_turn_id"]
    assert claim["quote"] == "I need help with my account."
    assert claim["start_ms"] == 100
    assert claim["end_ms"] == 900


def test_persists_false_resolution_evidence_and_exposes_manager_triage(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "calls.db",
        sample_data_dir=tmp_path / "samples",
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=1024,
    )
    with TestClient(create_test_app(settings)) as client:
        call_id = client.post(
            "/api/calls",
            data={"agent_name": "Agent", "customer_name": "Customer"},
            files={"audio": ("call.wav", b"audio", "audio/wav")},
        ).json()["call_id"]
        saved = client.put(
            f"/api/calls/{call_id}/transcript",
            json={
                "turns": [
                    {
                        "speaker": "agent",
                        "start_ms": 1000,
                        "end_ms": 1500,
                        "text": "Your card is fixed now.",
                    },
                    {
                        "speaker": "customer",
                        "start_ms": 3000,
                        "end_ms": 3500,
                        "text": "It still is not working.",
                    },
                ]
            },
        ).json()
        analysis = client.get(f"/api/calls/{call_id}/analysis").json()["analysis"]
        cached = client.get(f"/api/calls/{call_id}/analysis").json()["analysis"]
        triage = client.get("/api/dashboard/triage").json()["calls"]

    signal = analysis["false_resolution"]
    assert signal["rule_id"] == "false_resolution_contradiction_v1"
    assert signal["resolution"]["transcript_turn_id"] == saved["turns"][0]["transcript_turn_id"]
    assert signal["contradiction"]["transcript_turn_id"] == saved["turns"][1]["transcript_turn_id"]
    assert cached["false_resolution"] == signal
    assert triage[0]["analysis"]["false_resolution"] is True


def test_persists_repeated_question_events_with_saved_evidence(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "calls.db",
        sample_data_dir=tmp_path / "samples",
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=1024,
    )
    with TestClient(create_test_app(settings)) as client:
        call_id = client.post(
            "/api/calls",
            data={"agent_name": "Agent", "customer_name": "Customer"},
            files={"audio": ("call.wav", b"audio", "audio/wav")},
        ).json()["call_id"]
        saved = client.put(
            f"/api/calls/{call_id}/transcript",
            json={
                "turns": [
                    {
                        "speaker": "customer",
                        "start_ms": 1000,
                        "end_ms": 1500,
                        "text": "What time is my appointment?",
                    },
                    {
                        "speaker": "agent",
                        "start_ms": 2000,
                        "end_ms": 2500,
                        "text": "Let me check that for you.",
                    },
                    {
                        "speaker": "customer",
                        "start_ms": 3000,
                        "end_ms": 3500,
                        "text": "What time is my appointment?",
                    },
                ]
            },
        ).json()
        analysis = client.get(f"/api/calls/{call_id}/analysis").json()["analysis"]
        cached = client.get(f"/api/calls/{call_id}/analysis").json()["analysis"]

    assert len(analysis["repeated_questions"]) == 1
    event = analysis["repeated_questions"][0]
    assert event["rule_id"] == "repeated_question_exact_v1"
    assert event["speaker"] == "customer"
    assert event["original"]["transcript_turn_id"] == saved["turns"][0]["transcript_turn_id"]
    assert event["repeated"]["transcript_turn_id"] == saved["turns"][2]["transcript_turn_id"]
    assert cached["repeated_questions"] == analysis["repeated_questions"]


def test_replacing_a_transcript_invalidates_its_persisted_analysis(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "calls.db",
        sample_data_dir=tmp_path / "samples",
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=1024,
    )
    with TestClient(create_test_app(settings)) as client:
        call_id = client.post(
            "/api/calls",
            data={"agent_name": "Agent", "customer_name": "Customer"},
            files={"audio": ("call.wav", b"audio", "audio/wav")},
        ).json()["call_id"]
        client.put(
            f"/api/calls/{call_id}/transcript",
            json={"turns": [{"speaker": "customer", "start_ms": 0, "end_ms": 1, "text": "Help"}]},
        )
        client.get(f"/api/calls/{call_id}/analysis")
        client.put(
            f"/api/calls/{call_id}/transcript",
            json={
                "turns": [
                    {"speaker": "customer", "start_ms": 2, "end_ms": 3, "text": "All resolved"}
                ]
            },
        )

        triage = client.get("/api/dashboard/triage")
        regenerated = client.get(f"/api/calls/{call_id}/analysis")

    assert triage.json() == {"calls": []}
    assert regenerated.json()["analysis"]["claims"][0]["quote"] == "All resolved"


def test_returns_a_retriable_error_when_the_local_model_is_unavailable(tmp_path) -> None:
    class UnavailableProvider:
        def generate(self, turns: list[TranscriptTurn]) -> GeneratedAnalysis:
            raise AnalysisProviderError("local_model_unavailable")

    settings = Settings(
        database_path=tmp_path / "calls.db",
        sample_data_dir=tmp_path / "samples",
        upload_dir=tmp_path / "uploads",
    )
    app = create_app(settings)
    app.state.analysis_provider = UnavailableProvider()
    with TestClient(app) as client:
        call_id = client.post(
            "/api/calls",
            data={"agent_name": "Agent", "customer_name": "Customer"},
            files={"audio": ("call.wav", b"audio", "audio/wav")},
        ).json()["call_id"]
        client.put(
            f"/api/calls/{call_id}/transcript",
            json={"turns": [{"speaker": "customer", "start_ms": 0, "end_ms": 1, "text": "Help"}]},
        )
        response = client.get(f"/api/calls/{call_id}/analysis")

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Local analysis model is unavailable. Start Ollama and try again."
    )


def test_rejects_an_over_limit_summary_before_persistence(tmp_path) -> None:
    class LongSummaryProvider(FixtureAnalysisProvider):
        def generate(self, turns: list[TranscriptTurn]) -> GeneratedAnalysis:
            generated = super().generate(turns)
            payload = json.loads(generated.raw_output)
            payload["summary"] = "word " * (MAX_SUMMARY_WORDS + 1)
            return GeneratedAnalysis(
                raw_output=json.dumps(payload), model_version=generated.model_version
            )

    settings = Settings(
        database_path=tmp_path / "calls.db",
        sample_data_dir=tmp_path / "samples",
        upload_dir=tmp_path / "uploads",
    )
    app = create_app(settings)
    app.state.analysis_provider = LongSummaryProvider()
    with TestClient(app) as client:
        call_id = client.post(
            "/api/calls",
            data={"agent_name": "Agent", "customer_name": "Customer"},
            files={"audio": ("call.wav", b"audio", "audio/wav")},
        ).json()["call_id"]
        client.put(
            f"/api/calls/{call_id}/transcript",
            json={"turns": [{"speaker": "customer", "start_ms": 0, "end_ms": 1, "text": "Help"}]},
        )
        response = client.get(f"/api/calls/{call_id}/analysis")

    assert response.status_code == 502
    assert response.json()["detail"] == "Analysis output was invalid."
