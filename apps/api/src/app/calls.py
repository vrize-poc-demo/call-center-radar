from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from app.config import Settings
from app.logging import log_event

router = APIRouter(prefix="/api/calls", tags=["calls"])

SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav"}


class CallRegistration(BaseModel):
    call_id: str
    job_id: str
    status: str


@dataclass(frozen=True)
class UploadedCall:
    call_id: str
    job_id: str
    audio_path: Path


class CallRegistrationService:
    """Store a validated upload and create the initial queued job record."""

    def __init__(self, settings: Settings, database) -> None:
        self.settings = settings
        self.database = database

    def register(self, audio: UploadFile, agent_name: str, customer_name: str) -> UploadedCall:
        extension = Path(audio.filename or "").suffix.lower()
        if extension not in SUPPORTED_AUDIO_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Only MP3 and WAV audio files are supported.",
            )

        payload = audio.file.read(self.settings.max_upload_bytes + 1)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Audio is empty.",
            )
        if len(payload) > self.settings.max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Audio exceeds the configured upload limit.",
            )

        call_id = uuid4().hex
        job_id = f"job_{uuid4().hex}"
        upload_dir = self.settings.upload_dir
        if upload_dir is None:
            raise RuntimeError("Upload directory is not configured.")
        upload_dir.mkdir(parents=True, exist_ok=True)
        audio_path = upload_dir / f"{call_id}{extension}"

        try:
            audio_path.write_bytes(payload)
            with self.database.connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO calls (
                        call_id, audio_path, source_metadata_path, agent_name, customer_name
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        call_id,
                        str(audio_path),
                        f"upload://{call_id}",
                        agent_name,
                        customer_name,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO processing_jobs (job_id, call_id, status)
                    VALUES (?, ?, ?)
                    """,
                    (job_id, cursor.lastrowid, "queued"),
                )
        except Exception:
            audio_path.unlink(missing_ok=True)
            raise

        return UploadedCall(call_id=call_id, job_id=job_id, audio_path=audio_path)


@router.post("", response_model=CallRegistration, status_code=status.HTTP_201_CREATED)
async def register_call(
    request: Request,
    audio: UploadFile = File(...),
    agent_name: str = Form(..., min_length=1, max_length=120),
    customer_name: str = Form(..., min_length=1, max_length=120),
) -> CallRegistration:
    settings: Settings = request.app.state.settings
    logger = request.app.state.logger
    service = CallRegistrationService(settings, request.app.state.database)

    log_event(logger, "call_upload_received", "Call upload received")
    try:
        normalized_agent_name = agent_name.strip()
        normalized_customer_name = customer_name.strip()
        if not normalized_agent_name or not normalized_customer_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Agent and customer names are required.",
            )
        uploaded_call = service.register(audio, normalized_agent_name, normalized_customer_name)
    except HTTPException as error:
        log_event(
            logger,
            "call_upload_rejected",
            "Call upload rejected during validation",
            context={"status_code": error.status_code},
        )
        raise
    finally:
        await audio.close()

    log_event(
        logger,
        "call_registered",
        "Call and initial processing job registered",
        context={"call_id": uploaded_call.call_id, "job_id": uploaded_call.job_id},
    )
    return CallRegistration(
        call_id=uploaded_call.call_id,
        job_id=uploaded_call.job_id,
        status="queued",
    )
