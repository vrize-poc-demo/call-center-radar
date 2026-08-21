import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from app.config import Settings
from app.logging import log_event

router = APIRouter(prefix="/api/calls", tags=["calls"])

SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav"}
SUPPORTED_METADATA_EXTENSIONS = {".json"}


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

    def register(
        self,
        audio: UploadFile,
        metadata_payload: bytes,
        agent_name: str,
        customer_name: str,
    ) -> UploadedCall:
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
        metadata_path = upload_dir / f"{call_id}.json"

        try:
            audio_path.write_bytes(payload)
            metadata_path.write_bytes(metadata_payload)
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
                        str(metadata_path),
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
            metadata_path.unlink(missing_ok=True)
            raise

        return UploadedCall(call_id=call_id, job_id=job_id, audio_path=audio_path)


def read_participant_names(metadata: UploadFile, max_upload_bytes: int) -> tuple[str, str, bytes]:
    """Read the supported metadata file without retaining user-controlled names in logs."""

    extension = Path(metadata.filename or "").suffix.lower()
    if extension not in SUPPORTED_METADATA_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JSON metadata files are supported.",
        )

    payload = metadata.file.read(max_upload_bytes + 1)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Metadata is empty.",
        )
    if len(payload) > max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Metadata exceeds the configured upload limit.",
        )

    try:
        document = json.loads(payload)
        agent_name = document["agent"]["metadata"]["agent_name"].strip()
        customer_name = document["caller"]["metadata"]["first and last name"].strip()
    except (AttributeError, KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Metadata must be valid JSON with agent and caller names.",
        ) from None

    if not agent_name or not customer_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Metadata must include non-empty agent and caller names.",
        )
    if len(agent_name) > 120 or len(customer_name) > 120:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Metadata participant names must be at most 120 characters.",
        )
    return agent_name, customer_name, payload


@router.post("", response_model=CallRegistration, status_code=status.HTTP_201_CREATED)
async def register_call(
    request: Request,
    audio: UploadFile = File(...),
    metadata: UploadFile = File(...),
) -> CallRegistration:
    settings: Settings = request.app.state.settings
    logger = request.app.state.logger
    service = CallRegistrationService(settings, request.app.state.database)

    log_event(logger, "call_upload_received", "Call upload received")
    try:
        agent_name, customer_name, metadata_payload = read_participant_names(
            metadata, settings.max_upload_bytes
        )
        uploaded_call = service.register(audio, metadata_payload, agent_name, customer_name)
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
        await metadata.close()

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
