CREATE TABLE IF NOT EXISTS call_analysis_treatment_signals (
    id INTEGER PRIMARY KEY,
    analysis_id INTEGER NOT NULL REFERENCES call_analyses(id) ON DELETE CASCADE,
    rule_id TEXT NOT NULL,
    label TEXT NOT NULL,
    transcript_turn_id TEXT NOT NULL,
    UNIQUE(analysis_id, rule_id, transcript_turn_id)
);

CREATE INDEX IF NOT EXISTS idx_treatment_signals_analysis
    ON call_analysis_treatment_signals(analysis_id, id);
