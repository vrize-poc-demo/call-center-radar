ALTER TABLE processing_jobs ADD COLUMN audio_channels INTEGER;
ALTER TABLE processing_jobs ADD COLUMN failure_reason TEXT;

CREATE TABLE IF NOT EXISTS processing_job_events (
    id INTEGER PRIMARY KEY,
    processing_job_id INTEGER NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_processing_job_events_job_id
    ON processing_job_events(processing_job_id, id);
