import wave
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, status

from app.logging import log_event

PROCESSING_STATUSES = ("queued", "transcribing", "analyzing", "completed", "failed")
VALID_TRANSITIONS = {
    "queued": {"transcribing", "failed"},
    "transcribing": {"analyzing", "failed"},
    "analyzing": {"completed", "failed"},
    "completed": set(),
    "failed": set(),
}


@dataclass(frozen=True)
class ProcessingResult:
    job_id: str
    status: str
    audio_channels: int | None
    failure_reason: str | None


class ProcessingPipeline:
    """Small, durable pipeline skeleton; it deliberately performs no AI work."""

    def __init__(self, database, logger) -> None:
        self.database = database
        self.logger = logger

    def process(self, job_id: str) -> ProcessingResult:
        with self.database.connect() as connection:
            job = connection.execute(
                """
                SELECT processing_jobs.id, processing_jobs.job_id, processing_jobs.status,
                       calls.audio_path
                FROM processing_jobs JOIN calls ON calls.id = processing_jobs.call_id
                WHERE processing_jobs.job_id = ?
                """,
                (job_id,),
            ).fetchone()
            if job is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Processing job not found."
                )
            if job["status"] != "queued":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Processing job has already started.",
                )

            try:
                self._transition(connection, job, "transcribing")
                channels = self._validate_wav(Path(job["audio_path"]))
                self._transition(connection, job, "analyzing", audio_channels=channels)
                self._transition(connection, job, "completed", audio_channels=channels)
                return ProcessingResult(job_id, "completed", channels, None)
            except (OSError, wave.Error, ValueError):
                reason = "invalid_audio"
                self._transition(connection, job, "failed", failure_reason=reason)
                log_event(
                    self.logger,
                    "processing_failed",
                    "Audio processing validation failed",
                    context={"job_id": job_id, "reason": reason},
                )
                return ProcessingResult(job_id, "failed", None, reason)

    def _transition(
        self,
        connection,
        job,
        target: str,
        *,
        audio_channels: int | None = None,
        failure_reason: str | None = None,
    ) -> None:
        current = connection.execute(
            "SELECT status FROM processing_jobs WHERE id = ?", (job["id"],)
        ).fetchone()["status"]
        if target not in VALID_TRANSITIONS[current]:
            raise ValueError("invalid_state_transition")
        connection.execute(
            "UPDATE processing_jobs SET status = ?, audio_channels = COALESCE(?, audio_channels), "
            "failure_reason = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (target, audio_channels, failure_reason, job["id"]),
        )
        connection.execute(
            "INSERT INTO processing_job_events "
            "(processing_job_id, from_status, to_status, reason) VALUES (?, ?, ?, ?)",
            (job["id"], current, target, failure_reason),
        )
        log_event(
            self.logger,
            "processing_state_changed",
            "Processing job state changed",
            context={"job_id": job["job_id"], "from_status": current, "to_status": target},
        )

    @staticmethod
    def _validate_wav(path: Path) -> int:
        if path.suffix.lower() != ".wav":
            raise ValueError("unsupported_audio_validation")
        with wave.open(str(path), "rb") as audio:
            channels = audio.getnchannels()
            if channels not in {1, 2} or audio.getframerate() <= 0:
                raise ValueError("unsupported_audio")
            return channels
