ALTER TABLE processing_jobs ADD COLUMN queue_dismissed_at TEXT;

CREATE INDEX IF NOT EXISTS idx_processing_jobs_queue_dismissed_at
    ON processing_jobs(queue_dismissed_at);
