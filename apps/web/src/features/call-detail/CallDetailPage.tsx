import { useEffect, useRef, useState } from "react";

import {
  CallDetail,
  getCallAudioUrl,
  getCallDetail,
  getTranscript,
  TranscriptTurn,
} from "../../api/calls";

function formatPlaybackTime(milliseconds: number) {
  const totalSeconds = Math.floor(milliseconds / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function CallDetailPage({ callId }: { callId: string }) {
  const [detail, setDetail] = useState<CallDetail | null>(null);
  const [turns, setTurns] = useState<TranscriptTurn[]>([]);
  const [timeMs, setTimeMs] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const audio = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    let active = true;
    getCallDetail(callId)
      .then((value) => active && setDetail(value))
      .catch(
        (reason: unknown) =>
          active &&
          setError(
            reason instanceof Error
              ? reason.message
              : "The call detail could not be loaded.",
          ),
      );
    getTranscript(callId)
      .then((value) => active && setTurns(value))
      .catch(() => active && setTurns([]));
    return () => {
      active = false;
    };
  }, [callId]);

  const seekTo = (milliseconds: number) => {
    if (!audio.current) return;
    audio.current.currentTime = milliseconds / 1000;
    setTimeMs(milliseconds);
    const playback = audio.current.play();
    if (playback) {
      void playback.catch(() => console.warn("call_audio_playback_failed"));
    }
  };

  if (error)
    return (
      <main className="detail-page detail-message">
        <a className="back-link" href="/">
          Back to calls
        </a>
        <h1>Call detail unavailable</h1>
        <p role="alert">{error}</p>
      </main>
    );
  if (!detail)
    return (
      <main aria-busy="true" className="detail-page detail-message">
        <a className="back-link" href="/">
          Back to calls
        </a>
        <p className="eyebrow">Call detail</p>
        <h1>Loading call</h1>
        <p>
          Retrieving the recording, processing state, and transcript context.
        </p>
      </main>
    );

  const status = detail.processing_status.replaceAll("_", " ");
  return (
    <main className="detail-page">
      <a className="back-link" href="/">
        Back to calls
      </a>
      <header className="detail-header">
        <div>
          <p className="eyebrow">Call detail</p>
          <h1>{detail.customer_name}</h1>
          <p>Agent: {detail.agent_name}</p>
        </div>
        <span className={`status-badge status-${detail.processing_status}`}>
          {status}
        </span>
      </header>
      <div className="detail-grid">
        <section className="detail-panel audio-panel">
          <h2>Call recording</h2>
          <audio
            controls
            onError={() => console.warn("call_audio_load_failed")}
            onTimeUpdate={(event) =>
              setTimeMs(event.currentTarget.currentTime * 1000)
            }
            preload="metadata"
            ref={audio}
            src={getCallAudioUrl(detail.call_id)}
          >
            Your browser cannot play this call recording.
          </audio>
          <p aria-live="polite" className="playback-position">
            Playback position: {formatPlaybackTime(timeMs)}
          </p>
        </section>
        <section className="detail-panel">
          <h2>Processing</h2>
          <p>
            <strong>{status}</strong>
          </p>
          <p>
            {detail.failure_reason
              ? `Processing failed: ${detail.failure_reason}.`
              : detail.audio_channels === null
                ? "Audio validation has not completed."
                : `${detail.audio_channels === 1 ? "Mono" : "Stereo"} audio validated.`}
          </p>
        </section>
        <section className="detail-panel transcript-panel">
          <h2>Transcript</h2>
          <p>{detail.transcript_turn_count} saved turns</p>
          {turns.length ? (
            <ol className="transcript-turns">
              {turns.map((turn) => (
                <li
                  className={
                    timeMs >= turn.start_ms && timeMs < turn.end_ms
                      ? "active-turn"
                      : ""
                  }
                  key={turn.transcript_turn_id}
                >
                  <button onClick={() => seekTo(turn.start_ms)} type="button">
                    <span>{turn.speaker}</span>
                    <time>{(turn.start_ms / 1000).toFixed(1)}s</time>
                    <strong>{turn.text}</strong>
                  </button>
                </li>
              ))}
            </ol>
          ) : (
            <div className="empty-region">
              No transcript turns are saved for this call yet.
            </div>
          )}
        </section>
        <aside className="detail-panel evidence-panel">
          <h2>Evidence</h2>
          <div className="empty-region">
            Evidence-backed findings and score explanations will appear here in
            later stories.
          </div>
          <button
            className="jump-button"
            onClick={() => seekTo(0)}
            type="button"
          >
            Jump to call start
          </button>
        </aside>
      </div>
    </main>
  );
}
