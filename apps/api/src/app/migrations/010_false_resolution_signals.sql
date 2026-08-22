CREATE TABLE IF NOT EXISTS call_analysis_false_resolution_signals (
    analysis_id INTEGER PRIMARY KEY REFERENCES call_analyses(id) ON DELETE CASCADE,
    rule_id TEXT NOT NULL,
    resolution_transcript_turn_id TEXT NOT NULL,
    contradiction_transcript_turn_id TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_false_resolution_contradiction_turn
    ON call_analysis_false_resolution_signals(contradiction_transcript_turn_id);
