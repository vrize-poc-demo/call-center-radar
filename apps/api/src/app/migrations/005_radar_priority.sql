CREATE TABLE IF NOT EXISTS radar_priority_scores (
    id INTEGER PRIMARY KEY,
    call_id INTEGER NOT NULL UNIQUE REFERENCES calls(id) ON DELETE CASCADE,
    score INTEGER NOT NULL CHECK (score >= 0 AND score <= 100),
    scoring_version TEXT NOT NULL,
    calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS radar_priority_factors (
    id INTEGER PRIMARY KEY,
    score_id INTEGER NOT NULL REFERENCES radar_priority_scores(id) ON DELETE CASCADE,
    factor_key TEXT NOT NULL,
    label TEXT NOT NULL,
    contribution INTEGER NOT NULL CHECK (contribution > 0 AND contribution <= 100),
    evidence_id TEXT NOT NULL,
    transcript_turn_id TEXT NOT NULL,
    start_ms INTEGER NOT NULL CHECK (start_ms >= 0),
    end_ms INTEGER NOT NULL CHECK (end_ms >= start_ms)
);

CREATE INDEX IF NOT EXISTS idx_radar_priority_factors_score
    ON radar_priority_factors(score_id, id);
