CREATE TABLE IF NOT EXISTS call_analysis_repeated_question_events (
    id INTEGER PRIMARY KEY,
    analysis_id INTEGER NOT NULL REFERENCES call_analyses(id) ON DELETE CASCADE,
    rule_id TEXT NOT NULL,
    speaker TEXT NOT NULL CHECK (speaker IN ('agent', 'customer')),
    original_transcript_turn_id TEXT NOT NULL,
    repeated_transcript_turn_id TEXT NOT NULL,
    UNIQUE(analysis_id, repeated_transcript_turn_id)
);

CREATE INDEX IF NOT EXISTS idx_repeated_question_events_analysis
    ON call_analysis_repeated_question_events(analysis_id, id);
