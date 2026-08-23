CREATE TABLE transcript_turns_rebuilt (
    id INTEGER PRIMARY KEY,
    transcript_turn_id TEXT NOT NULL UNIQUE,
    call_id INTEGER NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    speaker TEXT NOT NULL,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (speaker IN ('agent', 'customer', 'unknown')),
    CHECK (start_ms >= 0),
    CHECK (end_ms >= start_ms)
);

INSERT INTO transcript_turns_rebuilt
    (id, transcript_turn_id, call_id, speaker, start_ms, end_ms, text, created_at)
SELECT id, transcript_turn_id, call_id, speaker, start_ms, end_ms, text, created_at
FROM transcript_turns;

DROP TABLE transcript_turns;
ALTER TABLE transcript_turns_rebuilt RENAME TO transcript_turns;

CREATE INDEX idx_transcript_turns_call_time
    ON transcript_turns(call_id, start_ms, id);
