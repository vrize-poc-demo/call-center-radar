CREATE TABLE IF NOT EXISTS call_analysis_mood_shifts (
    id INTEGER PRIMARY KEY,
    analysis_id INTEGER NOT NULL REFERENCES call_analyses(id) ON DELETE CASCADE,
    from_mood TEXT NOT NULL CHECK (from_mood IN ('positive', 'neutral', 'negative', 'mixed')),
    to_mood TEXT NOT NULL CHECK (to_mood IN ('positive', 'neutral', 'negative', 'mixed')),
    reason TEXT NOT NULL,
    transcript_turn_id TEXT NOT NULL,
    start_ms INTEGER NOT NULL CHECK (start_ms >= 0),
    end_ms INTEGER NOT NULL CHECK (end_ms >= start_ms)
);

CREATE INDEX IF NOT EXISTS idx_analysis_mood_shifts_analysis
    ON call_analysis_mood_shifts(analysis_id, start_ms, id);
