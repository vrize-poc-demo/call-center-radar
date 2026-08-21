import json
from pathlib import Path

from app.database import Database


def seed_sample_metadata(
    database: Database, sample_data_dir: Path, limit: int | None = None
) -> int:
    """Load a repeatable metadata-only seed set without reading audio content."""
    metadata_dir = sample_data_dir / "metadata"
    audio_dir = sample_data_dir / "audio"
    seeded = 0

    for metadata_file in sorted(metadata_dir.glob("*.json")):
        if metadata_file.stem.endswith(" 2"):
            continue
        if limit is not None and seeded >= limit:
            break

        payload = json.loads(metadata_file.read_text())
        call_id = payload.get("sid")
        if not call_id:
            continue

        agent = payload.get("agent", {})
        caller = payload.get("caller", {})
        audio_file = audio_dir / f"{call_id}.mp3"

        with database.connect() as connection:
            connection.execute(
                """
                INSERT INTO calls (
                    call_id, audio_path, source_metadata_path, agent_name, customer_name,
                    agent_speaker_id, customer_speaker_id, started_at_ms, ended_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(call_id) DO UPDATE SET
                    audio_path = excluded.audio_path,
                    source_metadata_path = excluded.source_metadata_path,
                    agent_name = excluded.agent_name,
                    customer_name = excluded.customer_name,
                    agent_speaker_id = excluded.agent_speaker_id,
                    customer_speaker_id = excluded.customer_speaker_id,
                    started_at_ms = excluded.started_at_ms,
                    ended_at_ms = excluded.ended_at_ms
                """,
                (
                    call_id,
                    str(audio_file) if audio_file.exists() else None,
                    str(metadata_file),
                    agent.get("metadata", {}).get("agent_name"),
                    caller.get("metadata", {}).get("first and last name"),
                    agent.get("speaker_id"),
                    caller.get("speaker_id"),
                    payload.get("start_time_ms"),
                    payload.get("end_time_ms"),
                ),
            )
        seeded += 1

    return seeded
