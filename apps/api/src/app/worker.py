from __future__ import annotations

import threading
from typing import Callable

from app.logging import log_event
from app.pipeline import ProcessingPipeline, ProcessingResult


class DurableProcessingWorker:
    """Run one local FIFO worker against durable SQLite processing jobs."""

    def __init__(
        self,
        database,
        logger,
        pipeline_factory: Callable[[], ProcessingPipeline],
    ) -> None:
        self.database = database
        self.logger = logger
        self.pipeline_factory = pipeline_factory
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        self.recover_interrupted_jobs()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="call-radar-processing-worker",
        )
        self._thread.start()
        log_event(self.logger, "processing_worker_started", "Local processing worker started")

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        log_event(self.logger, "processing_worker_stopped", "Local processing worker stopped")

    def enqueue(self, job_id: str) -> ProcessingResult:
        with self.database.connect() as connection:
            job = connection.execute(
                """
                SELECT job_id, status, audio_channels, failure_reason
                FROM processing_jobs WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
            if job is None:
                raise KeyError(job_id)
            queue_depth = connection.execute(
                "SELECT COUNT(*) FROM processing_jobs WHERE status = 'queued'"
            ).fetchone()[0]

        log_event(
            self.logger,
            "processing_enqueued",
            "Processing job accepted by the durable local queue",
            context={"job_id": job_id, "status": job["status"], "queue_depth": queue_depth},
        )
        self._wake_event.set()
        return ProcessingResult(job_id, job["status"], job["audio_channels"], job["failure_reason"])

    def recover_interrupted_jobs(self) -> int:
        with self.database.connect() as connection:
            jobs = connection.execute(
                """
                SELECT id, job_id, status FROM processing_jobs
                WHERE status IN ('transcribing', 'analyzing')
                ORDER BY id
                """
            ).fetchall()
            for job in jobs:
                connection.execute(
                    """
                    UPDATE processing_jobs
                    SET status = 'queued', failure_reason = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (job["id"],),
                )
                connection.execute(
                    """
                    INSERT INTO processing_job_events (
                        processing_job_id, from_status, to_status, reason
                    ) VALUES (?, ?, 'queued', 'worker_restart_recovery')
                    """,
                    (job["id"], job["status"]),
                )

        for job in jobs:
            log_event(
                self.logger,
                "processing_recovered_after_restart",
                "Interrupted processing job returned to the durable queue",
                context={"job_id": job["job_id"], "from_status": job["status"]},
            )
        return len(jobs)

    def fail_interrupted_jobs(self, reason: str) -> int:
        """Fail active jobs after an unexpected worker crash so the queue can advance."""
        with self.database.connect() as connection:
            jobs = connection.execute(
                """
                SELECT id, job_id, status FROM processing_jobs
                WHERE status IN ('transcribing', 'analyzing')
                ORDER BY id
                """
            ).fetchall()
            for job in jobs:
                connection.execute(
                    """
                    UPDATE processing_jobs
                    SET status = 'failed', failure_reason = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (reason, job["id"]),
                )
                connection.execute(
                    """
                    INSERT INTO processing_job_events (
                        processing_job_id, from_status, to_status, reason
                    ) VALUES (?, ?, 'failed', ?)
                    """,
                    (job["id"], job["status"], reason),
                )

        for job in jobs:
            log_event(
                self.logger,
                "processing_failed_after_worker_error",
                "Interrupted processing job failed after an unexpected worker error",
                context={"job_id": job["job_id"], "from_status": job["status"], "reason": reason},
            )
        return len(jobs)

    def run_once(self) -> ProcessingResult | None:
        result = self.pipeline_factory().process_next()
        if result is not None:
            log_event(
                self.logger,
                "processing_worker_finished_job",
                "Local processing worker finished a job",
                context={"job_id": result.job_id, "status": result.status},
            )
        return result

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                if self.run_once() is not None:
                    continue
            except Exception as error:
                failed_count = self.fail_interrupted_jobs("worker_error")
                log_event(
                    self.logger,
                    "processing_worker_error",
                    "Processing worker recovered from an unexpected error",
                    context={
                        "error_type": type(error).__name__,
                        "failed_interrupted_job_count": failed_count,
                    },
                )
            self._wake_event.wait(timeout=0.5)
            self._wake_event.clear()
