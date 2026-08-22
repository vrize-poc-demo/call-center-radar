CREATE TABLE IF NOT EXISTS call_analysis_silence_windows (
    id INTEGER PRIMARY KEY,
    analysis_id INTEGER NOT NULL REFERENCES call_analyses(id) ON DELETE CASCADE,
    before_transcript_turn_id TEXT NOT NULL,
    after_transcript_turn_id TEXT NOT NULL,
    duration_ms INTEGER NOT NULL CHECK (duration_ms >= 3000),
    UNIQUE(analysis_id, after_transcript_turn_id)
);

CREATE INDEX IF NOT EXISTS idx_silence_windows_analysis
    ON call_analysis_silence_windows(analysis_id, id);
