CREATE TABLE IF NOT EXISTS transcript_turns (
    id INTEGER PRIMARY KEY,
    transcript_turn_id TEXT NOT NULL UNIQUE,
    call_id INTEGER NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    speaker TEXT NOT NULL,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (speaker IN ('agent', 'customer')),
    CHECK (start_ms >= 0),
    CHECK (end_ms >= start_ms)
);

CREATE INDEX IF NOT EXISTS idx_transcript_turns_call_time
    ON transcript_turns(call_id, start_ms, id);
