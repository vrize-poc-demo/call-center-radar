import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class AudioInspectionError(ValueError):
    """Raised when ffprobe cannot identify a supported audio stream."""


class TranscriptionError(RuntimeError):
    """Raised when the configured local STT provider cannot produce a transcript."""


@dataclass(frozen=True)
class AudioInfo:
    channels: int
    duration_ms: int


@dataclass(frozen=True)
class TranscribedTurn:
    speaker: str
    start_ms: int
    end_ms: int
    text: str


class TranscriptionProvider(Protocol):
    @property
    def model_version(self) -> str: ...

    def transcribe(self, audio_path: Path, audio_info: AudioInfo) -> list[TranscribedTurn]: ...


def inspect_audio(audio_path: Path) -> AudioInfo:
    """Read codec-independent channel and duration information without loading audio into memory."""

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=channels,duration:format=duration",
                "-of",
                "json",
                str(audio_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        document = json.loads(result.stdout)
        stream = document["streams"][0]
        channels = int(stream["channels"])
        duration_seconds = stream.get("duration")
        if duration_seconds in {None, "N/A"}:
            duration_seconds = document.get("format", {}).get("duration")
        duration_ms = round(float(duration_seconds) * 1000)
    except (
        FileNotFoundError,
        IndexError,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as error:
        raise AudioInspectionError("invalid_audio") from error

    if channels not in {1, 2} or duration_ms <= 0:
        raise AudioInspectionError("unsupported_audio")
    return AudioInfo(channels=channels, duration_ms=duration_ms)


class FasterWhisperTranscriptionProvider:
    """Local STT provider with trustworthy stereo-channel attribution for the POC."""

    def __init__(
        self,
        model_name: str,
        device: str,
        *,
        left_speaker: str = "agent",
        right_speaker: str = "customer",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.left_speaker = left_speaker
        self.right_speaker = right_speaker
        self._model = None

    @property
    def model_version(self) -> str:
        return f"faster-whisper:{self.model_name}"

    def transcribe(self, audio_path: Path, audio_info: AudioInfo) -> list[TranscribedTurn]:
        try:
            if audio_info.channels == 1:
                return self._transcribe_file(audio_path, "unknown")
            with tempfile.TemporaryDirectory(prefix="call-radar-stt-") as directory:
                output_dir = Path(directory)
                left_audio = output_dir / "left.wav"
                right_audio = output_dir / "right.wav"
                self._extract_channel(audio_path, 0, left_audio)
                self._extract_channel(audio_path, 1, right_audio)
                turns = self._transcribe_file(left_audio, self.left_speaker)
                turns.extend(self._transcribe_file(right_audio, self.right_speaker))
                return sorted(turns, key=lambda turn: (turn.start_ms, turn.end_ms, turn.speaker))
        except (FileNotFoundError, OSError, subprocess.CalledProcessError, RuntimeError) as error:
            raise TranscriptionError("transcription_failed") from error

    def _extract_channel(self, source: Path, channel: int, destination: Path) -> None:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(source),
                "-map",
                "0:a:0",
                "-af",
                f"pan=mono|c0=c{channel}",
                "-ar",
                "16000",
                str(destination),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    def _transcribe_file(self, audio_path: Path, speaker: str) -> list[TranscribedTurn]:
        model = self._get_model()
        segments, _ = model.transcribe(
            str(audio_path),
            beam_size=5,
            language="en",
            vad_filter=True,
        )
        return [
            TranscribedTurn(
                speaker=speaker,
                start_ms=round(segment.start * 1000),
                end_ms=round(segment.end * 1000),
                text=segment.text.strip(),
            )
            for segment in segments
            if segment.text.strip()
        ]

    def _get_model(self):
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as error:
            raise TranscriptionError("transcription_provider_unavailable") from error
        self._model = WhisperModel(self.model_name, device=self.device, compute_type="int8")
        return self._model
