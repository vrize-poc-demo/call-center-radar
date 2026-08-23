from fastapi.testclient import TestClient

from app.config import Settings
from app.evidence import extract_evidence
from app.main import create_app
from app.transcripts import TranscriptTurn


def test_extract_evidence_links_exact_saved_turns() -> None:
    turn = TranscriptTurn(
        transcript_turn_id="turn_saved",
        speaker="customer",
        start_ms=1200,
        end_ms=1800,
        text="This issue is still not working.",
    )
    candidates = extract_evidence([turn])

    assert {candidate.rule_id for candidate in candidates} == {
        "unresolved_phrase",
        "problem_phrase",
    }
    assert all(candidate.transcript_turn_id == turn.transcript_turn_id for candidate in candidates)
    assert all(
        candidate.start_ms == 1200 and candidate.quote == turn.text for candidate in candidates
    )


def test_evidence_matching_is_case_insensitive_deterministic_and_non_mutating() -> None:
    turn = TranscriptTurn(
        transcript_turn_id="turn_stable",
        speaker="customer",
        start_ms=15,
        end_ms=45,
        text="I STILL CANNOT complete this request.",
    )

    first = extract_evidence([turn])
    second = extract_evidence([turn])

    assert [candidate.evidence_id for candidate in first] == [
        candidate.evidence_id for candidate in second
    ]
    assert [candidate.rule_id for candidate in first] == ["unresolved_phrase"]
    assert first[0].quote == turn.text
    assert (first[0].start_ms, first[0].end_ms) == (15, 45)


def test_evidence_matching_returns_empty_for_unrelated_or_empty_turn_sets() -> None:
    unrelated = TranscriptTurn(
        transcript_turn_id="turn_clear",
        speaker="customer",
        start_ms=0,
        end_ms=50,
        text="Thank you for confirming the delivery date.",
    )

    assert extract_evidence([]) == []
    assert extract_evidence([unrelated]) == []


def test_evidence_endpoint_reads_saved_transcript_turns(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "calls.db",
        sample_data_dir=tmp_path / "samples",
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=1024,
    )
    with TestClient(create_app(settings)) as client:
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
                        "end_ms": 500,
                        "text": "I need help with this error",
                    }
                ]
            },
        ).json()
        response = client.get(f"/api/calls/{call_id}/evidence")

    assert response.status_code == 200
    assert (
        response.json()["candidates"][0]["transcript_turn_id"]
        == saved["turns"][0]["transcript_turn_id"]
    )
    assert response.json()["candidates"][0]["quote"] == "I need help with this error"
