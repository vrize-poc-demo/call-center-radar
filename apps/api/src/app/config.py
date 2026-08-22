import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class Settings:
    database_path: Path
    sample_data_dir: Path
    log_level: str = "INFO"
    upload_dir: Path | None = None
    max_upload_bytes: int = 25 * 1024 * 1024
    transcription_model: str = "base.en"
    transcription_device: str = "cpu"
    stereo_left_speaker: str = "agent"
    stereo_right_speaker: str = "customer"

    @classmethod
    def from_environment(cls) -> "Settings":
        database_path = Path(os.getenv("CALL_RADAR_DATABASE_PATH", "data/call_radar.db"))
        sample_data_dir = Path(
            os.getenv("CALL_RADAR_SAMPLE_DATA_DIR", "sample-data/callradar-data")
        )

        return cls(
            database_path=_from_project_root(database_path),
            sample_data_dir=_from_project_root(sample_data_dir),
            log_level=os.getenv("CALL_RADAR_LOG_LEVEL", "INFO").upper(),
            upload_dir=_from_project_root(Path(os.getenv("CALL_RADAR_UPLOAD_DIR", "data/uploads"))),
            max_upload_bytes=int(os.getenv("CALL_RADAR_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024))),
            transcription_model=os.getenv("CALL_RADAR_TRANSCRIPTION_MODEL", "base.en"),
            transcription_device=os.getenv("CALL_RADAR_TRANSCRIPTION_DEVICE", "cpu"),
            stereo_left_speaker=os.getenv("CALL_RADAR_STEREO_LEFT_SPEAKER", "agent"),
            stereo_right_speaker=os.getenv("CALL_RADAR_STEREO_RIGHT_SPEAKER", "customer"),
        )


def _from_project_root(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path
