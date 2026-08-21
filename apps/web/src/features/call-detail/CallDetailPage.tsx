import { useEffect, useState } from "react";

import { CallDetail, getCallAudioUrl, getCallDetail } from "../../api/calls";

export function CallDetailPage({ callId }: { callId: string }) {
  const [detail, setDetail] = useState<CallDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getCallDetail(callId)
      .then((response) => active && setDetail(response))
      .catch(
        (reason: unknown) =>
          active &&
          setError(
            reason instanceof Error
              ? reason.message
              : "The call detail could not be loaded.",
          ),
      );
    return () => {
      active = false;
    };
  }, [callId]);

  if (error) {
    return (
      <main className="detail-page detail-message">
        <a className="back-link" href="/">
          Back to calls
        </a>
        <h1>Call detail unavailable</h1>
        <p role="alert">{error}</p>
      </main>
    );
  }
  if (!detail) {
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
  }

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
            preload="metadata"
            src={getCallAudioUrl(detail.call_id)}
          >
            Your browser cannot play this call recording.
          </audio>
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
          <div className="empty-region">
            Transcript rendering, timestamps, and sync arrive in Stories 2.2 and
            2.3.
          </div>
        </section>
        <aside className="detail-panel evidence-panel">
          <h2>Evidence</h2>
          <div className="empty-region">
            Evidence-backed findings and score explanations will appear here in
            later stories.
          </div>
        </aside>
      </div>
    </main>
  );
}
