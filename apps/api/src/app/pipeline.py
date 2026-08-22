import time
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, status

from app.logging import log_event
from app.transcription import (
    AudioInspectionError,
    FasterWhisperTranscriptionProvider,
    TranscriptionError,
    TranscriptionProvider,
    inspect_audio,
)
from app.transcripts import TranscriptTurnInput, replace_transcript_turns

PROCESSING_STATUSES = ("queued", "transcribing", "analyzing", "completed", "failed")
VALID_TRANSITIONS = {
    "queued": {"transcribing", "failed"},
    "transcribing": {"analyzing", "failed", "queued"},
    "analyzing": {"completed", "failed", "queued"},
    "completed": set(),
    "failed": set(),
}


@dataclass(frozen=True)
class ProcessingResult:
    job_id: str
    status: str
    audio_channels: int | None
    failure_reason: str | None
    transcript_turn_count: int = 0


@dataclass(frozen=True)
class ClaimedJob:
    id: int
    job_id: str
    call_id: str
    audio_path: Path


class ProcessingPipeline:
    """Durably transform uploaded audio into evidence-ready transcript turns."""

    def __init__(
        self, database, logger, settings, transcriber: TranscriptionProvider | None = None
    ) -> None:
        self.database = database
        self.logger = logger
        self.transcriber = transcriber or FasterWhisperTranscriptionProvider(
            settings.transcription_model,
            settings.transcription_device,
            left_speaker=settings.stereo_left_speaker,
            right_speaker=settings.stereo_right_speaker,
        )

    def process(self, job_id: str) -> ProcessingResult:
        claimed = self._claim(job_id=job_id)
        return self._process_claimed(claimed)

    def process_next(self) -> ProcessingResult | None:
        claimed = self._claim()
        return self._process_claimed(claimed) if claimed is not None else None

    def _claim(self, job_id: str | None = None) -> ClaimedJob | None:
        with self.database.connect() as connection:
            if job_id is None:
                job = connection.execute(
                    """
                    SELECT processing_jobs.id, processing_jobs.job_id, processing_jobs.status,
                           calls.call_id, calls.audio_path
                    FROM processing_jobs JOIN calls ON calls.id = processing_jobs.call_id
                    WHERE processing_jobs.status = 'queued'
                    ORDER BY processing_jobs.id ASC LIMIT 1
                    """
                ).fetchone()
                if job is None:
                    return None
            else:
                job = connection.execute(
                    """
                    SELECT processing_jobs.id, processing_jobs.job_id, processing_jobs.status,
                           calls.call_id, calls.audio_path
                    FROM processing_jobs JOIN calls ON calls.id = processing_jobs.call_id
                    WHERE processing_jobs.job_id = ?
                    """,
                    (job_id,),
                ).fetchone()
                if job is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Processing job not found.",
                    )
                if job["status"] != "queued":
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Processing job has already started.",
                    )
            self._transition(connection, job, "transcribing")
        return ClaimedJob(job["id"], job["job_id"], job["call_id"], Path(job["audio_path"]))

    def _process_claimed(self, job: ClaimedJob) -> ProcessingResult:
        try:
            audio_info = inspect_audio(job.audio_path)
            log_event(
                self.logger,
                "audio_inspected",
                "Uploaded audio inspected for transcription",
                context={
                    "job_id": job.job_id,
                    "audio_channels": audio_info.channels,
                    "audio_duration_ms": audio_info.duration_ms,
                },
            )
            started_at = time.monotonic()
            log_event(
                self.logger,
                "transcription_started",
                "Local transcription started",
                context={"job_id": job.job_id, "model_version": self.transcriber.model_version},
            )
            generated_turns = self.transcriber.transcribe(job.audio_path, audio_info)
            if not generated_turns:
                raise TranscriptionError("empty_transcript")
            saved_turns = replace_transcript_turns(
                self.database,
                job.call_id,
                [TranscriptTurnInput(**turn.__dict__) for turn in generated_turns],
            )
            elapsed_ms = round((time.monotonic() - started_at) * 1000)
            log_event(
                self.logger,
                "transcription_completed",
                "Local transcription completed",
                context={
                    "job_id": job.job_id,
                    "model_version": self.transcriber.model_version,
                    "processing_duration_ms": elapsed_ms,
                    "turn_count": len(saved_turns),
                },
            )
            with self.database.connect() as connection:
                row = self._load_job(connection, job.id)
                self._transition(connection, row, "analyzing", audio_channels=audio_info.channels)
                self._transition(connection, row, "completed", audio_channels=audio_info.channels)
            return ProcessingResult(
                job.job_id,
                "completed",
                audio_info.channels,
                None,
                len(saved_turns),
            )
        except AudioInspectionError:
            return self._fail(job, "invalid_audio")
        except (OSError, TranscriptionError, ValueError):
            return self._fail(job, "transcription_failed")

    def _fail(self, job: ClaimedJob, reason: str) -> ProcessingResult:
        with self.database.connect() as connection:
            self._transition(
                connection,
                self._load_job(connection, job.id),
                "failed",
                failure_reason=reason,
            )
        log_event(
            self.logger,
            "transcription_failed",
            "Audio processing or transcription failed",
            context={"job_id": job.job_id, "reason": reason},
        )
        return ProcessingResult(job.job_id, "failed", None, reason)

    @staticmethod
    def _load_job(connection, job_id: int):
        return connection.execute(
            "SELECT id, job_id, status FROM processing_jobs WHERE id = ?", (job_id,)
        ).fetchone()

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
