CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY,
    call_id TEXT NOT NULL UNIQUE,
    audio_path TEXT,
    source_metadata_path TEXT NOT NULL,
    agent_name TEXT,
    customer_name TEXT,
    agent_speaker_id INTEGER,
    customer_speaker_id INTEGER,
    started_at_ms INTEGER,
    ended_at_ms INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_calls_started_at_ms ON calls(started_at_ms);
