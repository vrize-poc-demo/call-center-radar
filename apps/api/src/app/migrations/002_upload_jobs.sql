CREATE TABLE IF NOT EXISTS processing_jobs (
    id INTEGER PRIMARY KEY,
    job_id TEXT NOT NULL UNIQUE,
    call_id INTEGER NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_processing_jobs_call_id ON processing_jobs(call_id);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_status ON processing_jobs(status);
