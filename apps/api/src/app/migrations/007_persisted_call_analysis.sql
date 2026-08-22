CREATE TABLE IF NOT EXISTS call_analyses (
    id INTEGER PRIMARY KEY,
    call_id INTEGER NOT NULL UNIQUE REFERENCES calls(id) ON DELETE CASCADE,
    intent TEXT NOT NULL,
    mood TEXT NOT NULL CHECK (mood IN ('positive', 'neutral', 'negative', 'mixed')),
    resolution TEXT NOT NULL CHECK (resolution IN ('resolved', 'unresolved', 'unclear')),
    summary TEXT NOT NULL,
    manager_brief TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    model_version TEXT NOT NULL,
    analysis_version INTEGER NOT NULL DEFAULT 1 CHECK (analysis_version >= 1),
    analyzed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS call_analysis_claims (
    id INTEGER PRIMARY KEY,
    analysis_id INTEGER NOT NULL REFERENCES call_analyses(id) ON DELETE CASCADE,
    claim TEXT NOT NULL,
    transcript_turn_id TEXT NOT NULL,
    start_ms INTEGER NOT NULL CHECK (start_ms >= 0),
    end_ms INTEGER NOT NULL CHECK (end_ms >= start_ms)
);

CREATE INDEX IF NOT EXISTS idx_call_analysis_claims_analysis
    ON call_analysis_claims(analysis_id, id);
