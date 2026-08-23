import json

from app.database import Database
from app.migrator import migrate
from app.seed import seed_sample_metadata


def test_migrations_are_versioned_and_idempotent(tmp_path) -> None:
    database = Database(tmp_path / "call_radar.db")

    assert migrate(database) == [
        "001_initial.sql",
        "002_upload_jobs.sql",
        "003_processing_pipeline.sql",
        "004_transcript_turns.sql",
        "005_radar_priority.sql",
        "006_unknown_transcript_speaker.sql",
        "007_persisted_call_analysis.sql",
        "008_processing_queue_dismissal.sql",
        "009_analysis_mood_shifts.sql",
        "010_false_resolution_signals.sql",
        "011_repeated_question_events.sql",
        "012_silence_windows.sql",
        "013_customer_history.sql",
    ]
    assert migrate(database) == []

    with database.connect() as connection:
        assert connection.execute("SELECT version FROM schema_migrations").fetchone()[
            "version"
        ] == ("001_initial.sql")


def test_seed_imports_metadata_without_reading_audio(tmp_path) -> None:
    sample_data_dir = tmp_path / "sample-data"
    metadata_dir = sample_data_dir / "metadata"
    metadata_dir.mkdir(parents=True)
    (metadata_dir / "call-1.json").write_text(
        json.dumps(
            {
                "sid": "call-1",
                "start_time_ms": 100,
                "end_time_ms": 200,
                "agent": {"speaker_id": 1, "metadata": {"agent_name": "Agent One"}},
                "caller": {"speaker_id": 2, "metadata": {"first and last name": "Caller One"}},
            }
        )
    )
    database = Database(tmp_path / "call_radar.db")
    migrate(database)

    assert seed_sample_metadata(database, sample_data_dir) == 1

    with database.connect() as connection:
        call = connection.execute(
            "SELECT call_id, audio_path, agent_name, customer_name FROM calls"
        ).fetchone()

    assert dict(call) == {
        "call_id": "call-1",
        "audio_path": None,
        "agent_name": "Agent One",
        "customer_name": "Caller One",
    }
