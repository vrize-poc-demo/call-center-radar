import subprocess
from pathlib import Path

import pytest

from app.transcription import (
    AudioInfo,
    AudioInspectionError,
    FasterWhisperTranscriptionProvider,
    TranscribedTurn,
    inspect_audio,
)


def test_inspect_audio_reads_wav_channel_count_and_duration(tmp_path, monkeypatch) -> None:
    def ffprobe_result(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=(
                '{"streams": [{"channels": 2, "duration": "1.0"}], "format": {"duration": "1.0"}}'
            ),
        )

    monkeypatch.setattr(subprocess, "run", ffprobe_result)

    inspected = inspect_audio(tmp_path / "stereo.wav")

    assert inspected.channels == 2
    assert inspected.duration_ms == 1000


def test_inspect_audio_rejects_unreadable_audio(tmp_path) -> None:
    audio_path = tmp_path / "not-audio.mp3"
    audio_path.write_bytes(b"not audio")

    with pytest.raises(AudioInspectionError):
        inspect_audio(audio_path)


def test_inspect_audio_uses_container_duration_when_stream_duration_is_unavailable(
    monkeypatch, tmp_path
) -> None:
    def ffprobe_result(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=(
                '{"streams": [{"channels": 1, "duration": "N/A"}], "format": {"duration": "2.5"}}'
            ),
        )

    monkeypatch.setattr(subprocess, "run", ffprobe_result)

    inspected = inspect_audio(tmp_path / "source.wav")

    assert inspected == AudioInfo(channels=1, duration_ms=2500)


def test_stereo_provider_assigns_configured_channel_speakers(monkeypatch, tmp_path) -> None:
    provider = FasterWhisperTranscriptionProvider(
        "base.en",
        "cpu",
        left_speaker="customer",
        right_speaker="agent",
    )
    extracted = []

    def extract(source, channel, destination) -> None:
        extracted.append((source, channel, destination.name))

    def transcribe(audio_path, speaker) -> list[TranscribedTurn]:
        start_ms = 100 if speaker == "customer" else 0
        return [TranscribedTurn(speaker=speaker, start_ms=start_ms, end_ms=200, text=speaker)]

    monkeypatch.setattr(provider, "_extract_channel", extract)
    monkeypatch.setattr(provider, "_transcribe_file", transcribe)

    turns = provider.transcribe(tmp_path / "source.mp3", AudioInfo(channels=2, duration_ms=500))

    assert [(channel, name) for _, channel, name in extracted] == [
        (0, "left.wav"),
        (1, "right.wav"),
    ]
    assert [turn.speaker for turn in turns] == ["agent", "customer"]


def test_mono_provider_keeps_speaker_unknown(monkeypatch, tmp_path) -> None:
    provider = FasterWhisperTranscriptionProvider("base.en", "cpu")
    captured_speakers = []

    def transcribe(audio_path, speaker) -> list[TranscribedTurn]:
        captured_speakers.append(speaker)
        return [TranscribedTurn(speaker=speaker, start_ms=0, end_ms=100, text="Hello")]

    monkeypatch.setattr(provider, "_transcribe_file", transcribe)

    turns = provider.transcribe(
        Path(tmp_path / "source.mp3"), AudioInfo(channels=1, duration_ms=500)
    )

    assert captured_speakers == ["unknown"]
    assert turns[0].speaker == "unknown"
