ALTER TABLE processing_jobs ADD COLUMN trace_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_processing_jobs_trace_id
    ON processing_jobs(trace_id)
    WHERE trace_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS trace_events (
    id INTEGER PRIMARY KEY,
    trace_id TEXT NOT NULL,
    request_id TEXT,
    call_id INTEGER REFERENCES calls(id) ON DELETE CASCADE,
    processing_job_id INTEGER REFERENCES processing_jobs(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('started', 'succeeded', 'failed', 'transitioned')),
    model_version TEXT,
    rule_version TEXT,
    validation_result TEXT,
    failure_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trace_events_trace_id
    ON trace_events(trace_id, id);

CREATE INDEX IF NOT EXISTS idx_trace_events_call_id
    ON trace_events(call_id, id);
