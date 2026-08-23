import { useEffect, useRef, useState } from "react";

import {
  CallAnalysis,
  CallDetail,
  calculatePriority,
  EvidenceCandidate,
  EvidenceClaim,
  FalseResolutionSignal,
  getAnalysis,
  getCallAudioUrl,
  getCallDetail,
  getEvidence,
  getTranscript,
  PriorityFactor,
  RadarPriority,
  RepeatedQuestionEvent,
  SilenceWindow,
  TreatmentSignal,
  MoodShift,
  TranscriptTurn,
} from "../../api/calls";
import { selectActiveTranscriptTurn } from "./transcriptPlayback";
import { buildTranscriptSequence } from "./transcriptSequence";

function formatPlaybackTime(milliseconds: number) {
  const totalSeconds = Math.floor(milliseconds / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function formatTranscriptRange(turn: TranscriptTurn) {
  return `${(turn.start_ms / 1000).toFixed(2)}s–${(turn.end_ms / 1000).toFixed(2)}s`;
}

function formatTranscriptGroupRange(startMs: number, endMs: number) {
  return `${(startMs / 1000).toFixed(2)}s–${(endMs / 1000).toFixed(2)}s`;
}

type SpeakerFilter = "all" | TranscriptTurn["speaker"];

type EvidenceTrace = {
  title: string;
  detail: string;
  transcript_turn_id: string;
  start_ms: number;
  end_ms: number;
  contribution?: number;
  evidence_id?: string;
  broken: boolean;
};

export function CallDetailPage({ callId }: { callId: string }) {
  const [detail, setDetail] = useState<CallDetail | null>(null);
  const [turns, setTurns] = useState<TranscriptTurn[]>([]);
  const [evidence, setEvidence] = useState<EvidenceCandidate[]>([]);
  const [priority, setPriority] = useState<RadarPriority | null>(null);
  const [analysis, setAnalysis] = useState<CallAnalysis | null>(null);
  const [selectedTrace, setSelectedTrace] = useState<EvidenceTrace | null>(
    null,
  );
  const [showScoreExplanation, setShowScoreExplanation] = useState(false);
  const [timeMs, setTimeMs] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [speakerFilter, setSpeakerFilter] = useState<SpeakerFilter>("all");
  const audio = useRef<HTMLAudioElement>(null);
  const turnElements = useRef(new Map<string, HTMLElement>());

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
      .catch(() => {
        console.warn("transcript_load_failed");
        if (active) setTurns([]);
      });
    getEvidence(callId)
      .then((value) => active && setEvidence(value))
      .catch(() => console.warn("evidence_load_failed"));
    calculatePriority(callId)
      .then((value) => active && setPriority(value))
      .catch(() => console.warn("radar_priority_load_failed"));
    getAnalysis(callId)
      .then((value) => active && setAnalysis(value))
      .catch(() => console.warn("analysis_load_failed"));
    return () => {
      active = false;
    };
  }, [callId]);

  useEffect(() => {
    if (
      detail?.processing_status === "completed" ||
      detail?.processing_status === "failed"
    ) {
      return;
    }

    let active = true;
    const refreshCompletedContext = () => {
      void getTranscript(callId)
        .then((value) => active && setTurns(value))
        .catch(() => console.warn("transcript_load_failed"));
      void getEvidence(callId)
        .then((value) => active && setEvidence(value))
        .catch(() => console.warn("evidence_load_failed"));
    };
    const refreshDetail = () => {
      void getCallDetail(callId)
        .then((value) => {
          if (!active) return;
          setDetail(value);
          if (value.processing_status === "completed") {
            refreshCompletedContext();
            window.clearInterval(intervalId);
          }
          if (value.processing_status === "failed")
            window.clearInterval(intervalId);
        })
        .catch(() => console.warn("call_detail_refresh_failed"));
    };
    const intervalId = window.setInterval(refreshDetail, 3_000);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [callId, detail?.processing_status]);

  const seekTo = (milliseconds: number) => {
    if (!audio.current) return;
    audio.current.currentTime = milliseconds / 1000;
    setTimeMs(milliseconds);
    const playback = audio.current.play();
    if (playback) {
      void playback.catch(() => console.warn("call_audio_playback_failed"));
    }
  };

  const activeTurn = selectActiveTranscriptTurn(turns, timeMs);

  useEffect(() => {
    if (!activeTurn) return;
    const activeElement = turnElements.current.get(
      activeTurn.transcript_turn_id,
    );
    if (!activeElement?.scrollIntoView) return;

    try {
      activeElement.scrollIntoView({ block: "nearest" });
    } catch {
      console.warn("transcript_active_turn_scroll_failed");
    }
  }, [activeTurn]);

  const normalizedSearchTerm = searchTerm.trim().toLocaleLowerCase();
  const visibleTurns = turns.filter((turn) => {
    const matchesSpeaker =
      speakerFilter === "all" || turn.speaker === speakerFilter;
    const matchesSearch = turn.text
      .toLocaleLowerCase()
      .includes(normalizedSearchTerm);
    return (
      turn.transcript_turn_id === activeTurn?.transcript_turn_id ||
      (matchesSpeaker && matchesSearch)
    );
  });
  const transcriptSequence = buildTranscriptSequence(visibleTurns);

  const updateSearchTerm = (value: string) => {
    setSearchTerm(value);
    console.info("transcript_search_updated", {
      query_length: value.length,
      speaker_filter: speakerFilter,
    });
  };

  const updateSpeakerFilter = (value: SpeakerFilter) => {
    setSpeakerFilter(value);
    console.info("transcript_search_updated", {
      query_length: searchTerm.length,
      speaker_filter: value,
    });
  };

  const openTrace = (
    source: "priority_factor" | "analysis_claim",
    trace: PriorityFactor | EvidenceClaim,
  ) => {
    const matchingTurn = turns.find(
      (turn) => turn.transcript_turn_id === trace.transcript_turn_id,
    );
    const factor = "factor_key" in trace ? trace : null;
    const evidenceTrace: EvidenceTrace = {
      title: factor ? factor.label : "Analysis claim",
      detail:
        "claim" in trace
          ? trace.claim
          : (matchingTurn?.text ?? "Transcript evidence is unavailable."),
      transcript_turn_id: trace.transcript_turn_id,
      start_ms: trace.start_ms,
      end_ms: trace.end_ms,
      contribution: factor?.contribution,
      evidence_id: factor?.evidence_id,
      broken: !matchingTurn,
    };
    setSelectedTrace(evidenceTrace);
    if (!matchingTurn) {
      console.warn("evidence_trace_link_broken", {
        call_id: callId,
        source,
        transcript_turn_id: trace.transcript_turn_id,
        evidence_id: factor?.evidence_id,
      });
      return;
    }
    console.info("evidence_opened", {
      call_id: callId,
      source,
      transcript_turn_id: trace.transcript_turn_id,
      evidence_id: factor?.evidence_id,
    });
    seekTo(trace.start_ms);
  };

  const openMoodShift = (shift: MoodShift) => {
    const matchingTurn = turns.find(
      (turn) => turn.transcript_turn_id === shift.transcript_turn_id,
    );
    const trace: EvidenceTrace = {
      title: `Mood shift: ${shift.from_mood} to ${shift.to_mood}`,
      detail: shift.reason,
      transcript_turn_id: shift.transcript_turn_id,
      start_ms: shift.start_ms,
      end_ms: shift.end_ms,
      broken: !matchingTurn,
    };
    setSelectedTrace(trace);
    if (!matchingTurn) {
      console.warn("mood_shift_link_broken", {
        call_id: callId,
        transcript_turn_id: shift.transcript_turn_id,
      });
      return;
    }
    console.info("mood_shift_opened", {
      call_id: callId,
      transcript_turn_id: shift.transcript_turn_id,
    });
    seekTo(shift.start_ms);
  };

  const openFalseResolutionEvidence = (
    signal: FalseResolutionSignal,
    source: "resolution" | "contradiction",
  ) => {
    openTrace("analysis_claim", signal[source]);
  };

  const openRepeatedQuestionEvidence = (
    event: RepeatedQuestionEvent,
    source: "original" | "repeated",
  ) => {
    openTrace("analysis_claim", event[source]);
  };

  const openTreatmentSignalEvidence = (signal: TreatmentSignal) => {
    openTrace("analysis_claim", signal.evidence);
  };

  const openSilenceEvidence = (
    window: SilenceWindow,
    source: "before" | "after",
  ) => {
    openTrace("analysis_claim", window[source]);
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
        <section className="detail-panel transcript-panel">
          <h2>Transcript</h2>
          <p>{detail.transcript_turn_count} saved turns</p>
          {turns.length ? (
            <>
              <div className="transcript-controls">
                <label>
                  Search transcript
                  <input
                    onChange={(event) => updateSearchTerm(event.target.value)}
                    placeholder="Find a phrase"
                    type="search"
                    value={searchTerm}
                  />
                </label>
                <label>
                  Show speaker
                  <select
                    onChange={(event) =>
                      updateSpeakerFilter(event.target.value as SpeakerFilter)
                    }
                    value={speakerFilter}
                  >
                    <option value="all">All speakers</option>
                    <option value="agent">Agent</option>
                    <option value="customer">Customer</option>
                    <option value="unknown">Unknown speaker</option>
                  </select>
                </label>
              </div>
              <p aria-live="polite" className="transcript-result-count">
                Showing {visibleTurns.length} of {turns.length} turns
              </p>
              {activeTurn &&
              !(
                (speakerFilter === "all" ||
                  activeTurn.speaker === speakerFilter) &&
                activeTurn.text
                  .toLocaleLowerCase()
                  .includes(normalizedSearchTerm)
              ) ? (
                <p className="active-turn-note">
                  Showing the active turn alongside your filters.
                </p>
              ) : null}
              {visibleTurns.length ? (
                <div className="transcript-sequence">
                  <div aria-hidden="true" className="transcript-lane-headings">
                    <strong>Customer</strong>
                    <strong>Agent</strong>
                  </div>
                  <ol
                    aria-label="Chronological transcript"
                    className="transcript-groups"
                  >
                    {transcriptSequence.map((group, index) => (
                      <li
                        aria-label={
                          group.has_overlap
                            ? `Overlapping transcript group ${index + 1}`
                            : `Transcript group ${index + 1}`
                        }
                        className={group.has_overlap ? "overlap-group" : ""}
                        key={group.id}
                      >
                        <div className="transcript-group-meta">
                          <span>
                            Sequence {index + 1}
                            {group.has_overlap
                              ? ` · Shared time ${formatTranscriptGroupRange(group.start_ms, group.end_ms)}`
                              : null}
                          </span>
                          {group.has_overlap ? (
                            <span>
                              Timing overlaps; exact sentence order is
                              unavailable.
                            </span>
                          ) : null}
                        </div>
                        <div className="transcript-group-lanes">
                          {(["customer", "agent"] as const).map((speaker) => (
                            <div
                              aria-label={`${speaker === "customer" ? "Customer" : "Agent"} messages in sequence ${index + 1}`}
                              className={`transcript-lane ${speaker}-lane`}
                              key={speaker}
                            >
                              {group.turns
                                .filter((turn) => turn.speaker === speaker)
                                .map((turn) => {
                                  const isActive =
                                    turn.transcript_turn_id ===
                                    activeTurn?.transcript_turn_id;
                                  return (
                                    <div
                                      className={isActive ? "active-turn" : ""}
                                      key={turn.transcript_turn_id}
                                      ref={(element) => {
                                        if (element)
                                          turnElements.current.set(
                                            turn.transcript_turn_id,
                                            element,
                                          );
                                        else
                                          turnElements.current.delete(
                                            turn.transcript_turn_id,
                                          );
                                      }}
                                    >
                                      <button
                                        onClick={() => seekTo(turn.start_ms)}
                                        type="button"
                                      >
                                        <span className="mobile-speaker-label">
                                          {speaker === "customer"
                                            ? "Customer"
                                            : "Agent"}
                                        </span>
                                        <time>
                                          {formatTranscriptRange(turn)}
                                        </time>
                                        <strong>{turn.text}</strong>
                                      </button>
                                    </div>
                                  );
                                })}
                            </div>
                          ))}
                          {group.turns
                            .filter((turn) => turn.speaker === "unknown")
                            .map((turn) => (
                              <div
                                className={`transcript-lane unknown-lane ${
                                  turn.transcript_turn_id ===
                                  activeTurn?.transcript_turn_id
                                    ? "active-turn"
                                    : ""
                                }`}
                                key={turn.transcript_turn_id}
                                ref={(element) => {
                                  if (element)
                                    turnElements.current.set(
                                      turn.transcript_turn_id,
                                      element,
                                    );
                                  else
                                    turnElements.current.delete(
                                      turn.transcript_turn_id,
                                    );
                                }}
                              >
                                <span className="unknown-speaker-label">
                                  Unattributed
                                </span>
                                <button
                                  onClick={() => seekTo(turn.start_ms)}
                                  type="button"
                                >
                                  <time>{formatTranscriptRange(turn)}</time>
                                  <strong>{turn.text}</strong>
                                </button>
                              </div>
                            ))}
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
              ) : (
                <div className="empty-region">
                  No saved transcript turns match these filters.
                </div>
              )}
            </>
          ) : (
            <div className="empty-region">
              No transcript turns are saved for this call yet.
            </div>
          )}
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
        <aside className="detail-panel priority-panel">
          <h2>Radar Priority</h2>
          {priority ? (
            <>
              <p className="priority-score">
                <strong>{priority.score}</strong> / 100
              </p>
              <p className="supporting-copy">
                {priority.factors.length
                  ? "This score has evidence you can inspect."
                  : "No priority factors matched this call."}
              </p>
              {priority.factors.length ? (
                <button
                  className="jump-button"
                  onClick={() => {
                    setSelectedTrace(null);
                    setShowScoreExplanation(true);
                  }}
                  type="button"
                >
                  Show me why
                </button>
              ) : null}
            </>
          ) : (
            <div className="empty-region">
              Radar Priority is unavailable for this call.
            </div>
          )}
        </aside>
        <section className="detail-panel analysis-panel">
          <h2>Call analysis</h2>
          {analysis ? (
            <>
              <h3>Summary</h3>
              <p>{analysis.summary}</p>
              <h3>Manager brief</h3>
              <p>{analysis.manager_brief}</p>
              {analysis.false_resolution ? (
                <section
                  className="false-resolution"
                  aria-label="Resolution check"
                >
                  <h3>Resolution check</h3>
                  <p>
                    A stated resolution was later contradicted by the customer.
                  </p>
                  <div className="false-resolution-actions">
                    <button
                      onClick={() =>
                        openFalseResolutionEvidence(
                          analysis.false_resolution!,
                          "resolution",
                        )
                      }
                      type="button"
                    >
                      Show stated resolution
                    </button>
                    <button
                      onClick={() =>
                        openFalseResolutionEvidence(
                          analysis.false_resolution!,
                          "contradiction",
                        )
                      }
                      type="button"
                    >
                      Show later contradiction
                    </button>
                  </div>
                </section>
              ) : null}
              <h3>Repeated information requests</h3>
              {analysis.repeated_questions.length ? (
                <ol className="repeated-question-events">
                  {analysis.repeated_questions.map((event) => (
                    <li key={event.repeated.transcript_turn_id}>
                      <strong>{event.speaker} repeated a question</strong>
                      <span>
                        {(event.repeated.start_ms / 1000).toFixed(1)}s
                      </span>
                      <div>
                        <button
                          onClick={() =>
                            openRepeatedQuestionEvidence(event, "original")
                          }
                          type="button"
                        >
                          Show original
                        </button>
                        <button
                          onClick={() =>
                            openRepeatedQuestionEvidence(event, "repeated")
                          }
                          type="button"
                        >
                          Show repeat
                        </button>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="supporting-copy">
                  No repeated information requests were detected.
                </p>
              )}
              <h3>Customer treatment signals</h3>
              {(analysis.treatment_signals ?? []).length ? (
                <ol className="repeated-question-events">
                  {(analysis.treatment_signals ?? []).map((signal) => (
                    <li
                      key={`${signal.rule_id}-${signal.evidence.transcript_turn_id}`}
                    >
                      <strong>{signal.label}</strong>
                      <span>
                        {(signal.evidence.start_ms / 1000).toFixed(1)}s
                      </span>
                      <div>
                        <button
                          onClick={() => openTreatmentSignalEvidence(signal)}
                          type="button"
                        >
                          Show transcript evidence
                        </button>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="supporting-copy">
                  No evidence-backed customer treatment signals were detected.
                </p>
              )}
              <h3>Conversation balance</h3>
              {analysis.conversation_balance.agent_talk_ms ||
              analysis.conversation_balance.customer_talk_ms ? (
                <>
                  <div
                    className="conversation-balance-bar"
                    aria-label="Attributed talk balance"
                  >
                    <span
                      className="agent-balance"
                      style={{
                        width: `${analysis.conversation_balance.agent_share_pct}%`,
                      }}
                    />
                    <span
                      className="customer-balance"
                      style={{
                        width: `${analysis.conversation_balance.customer_share_pct}%`,
                      }}
                    />
                  </div>
                  <p className="conversation-balance-labels">
                    Agent {analysis.conversation_balance.agent_share_pct}% ·
                    Customer {analysis.conversation_balance.customer_share_pct}%
                    of attributed speech
                  </p>
                </>
              ) : (
                <p className="supporting-copy">
                  Speaker labels are unavailable for talk-balance calculation.
                </p>
              )}
              <h3>Silence windows</h3>
              {analysis.silence_windows.length ? (
                <ol className="silence-windows">
                  {analysis.silence_windows.map((window) => (
                    <li key={window.after.transcript_turn_id}>
                      <strong>
                        {(window.duration_ms / 1000).toFixed(1)}s silence
                      </strong>
                      <span>
                        {(window.before.end_ms / 1000).toFixed(1)}s to{" "}
                        {(window.after.start_ms / 1000).toFixed(1)}s
                      </span>
                      <div>
                        <button
                          onClick={() => openSilenceEvidence(window, "before")}
                          type="button"
                        >
                          Show before
                        </button>
                        <button
                          onClick={() => openSilenceEvidence(window, "after")}
                          type="button"
                        >
                          Show after
                        </button>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="supporting-copy">
                  No silence windows of three seconds or longer were detected.
                </p>
              )}
              <h3>Mood timeline</h3>
              <p className="mood-overall">Overall mood: {analysis.mood}</p>
              {analysis.mood_shifts.length ? (
                <ol className="evidence-candidates mood-shifts">
                  {analysis.mood_shifts.map((shift) => (
                    <li key={`${shift.transcript_turn_id}-${shift.to_mood}`}>
                      <button
                        onClick={() => openMoodShift(shift)}
                        type="button"
                      >
                        <strong>
                          {shift.from_mood} to {shift.to_mood}
                        </strong>
                        <time>{(shift.start_ms / 1000).toFixed(1)}s</time>
                        <span>{shift.reason}</span>
                      </button>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="supporting-copy">
                  No evidence-backed mood shift was detected.
                </p>
              )}
              <h3>Evidence-backed claims</h3>
              {analysis.claims.length ? (
                <ol className="evidence-candidates">
                  {analysis.claims.map((claim) => (
                    <li key={`${claim.transcript_turn_id}-${claim.claim}`}>
                      <button
                        onClick={() => openTrace("analysis_claim", claim)}
                        type="button"
                      >
                        <strong>{claim.claim}</strong>
                        <time>{(claim.start_ms / 1000).toFixed(1)}s</time>
                        <span>Show transcript evidence</span>
                      </button>
                    </li>
                  ))}
                </ol>
              ) : (
                <div className="empty-region">
                  No evidence-backed claims were returned.
                </div>
              )}
            </>
          ) : (
            <div className="empty-region">
              Analysis is unavailable for this call.
            </div>
          )}
        </section>
        <aside className="detail-panel evidence-panel">
          <h2>Evidence</h2>
          {evidence.length ? (
            <ol className="evidence-candidates">
              {evidence.map((candidate) => (
                <li key={candidate.evidence_id}>
                  <button
                    onClick={() => seekTo(candidate.start_ms)}
                    type="button"
                  >
                    <strong>{candidate.label}</strong>
                    <time>{(candidate.start_ms / 1000).toFixed(1)}s</time>
                    <span>{candidate.quote}</span>
                  </button>
                </li>
              ))}
            </ol>
          ) : (
            <div className="empty-region">
              No deterministic evidence candidates were found.
            </div>
          )}
          <button
            className="jump-button"
            onClick={() => seekTo(0)}
            type="button"
          >
            Jump to call start
          </button>
        </aside>
      </div>
      {showScoreExplanation || selectedTrace ? (
        <aside
          aria-labelledby="evidence-drawer-title"
          className="evidence-drawer"
          role="dialog"
        >
          <div className="evidence-drawer-header">
            <h2 id="evidence-drawer-title">
              {selectedTrace ? "Evidence details" : "Why your score is high"}
            </h2>
            <button
              onClick={() => {
                setSelectedTrace(null);
                setShowScoreExplanation(false);
              }}
              type="button"
            >
              Close
            </button>
          </div>
          {selectedTrace ? (
            <>
              {showScoreExplanation ? (
                <button
                  className="drawer-back-button"
                  onClick={() => setSelectedTrace(null)}
                  type="button"
                >
                  Back to score factors
                </button>
              ) : null}
              <p>
                <strong>{selectedTrace.title}</strong>
                {selectedTrace.contribution
                  ? ` (+${selectedTrace.contribution} points)`
                  : ""}
              </p>
              <p>{selectedTrace.detail}</p>
              <p className="trace-meta">
                Transcript turn: {selectedTrace.transcript_turn_id} at{" "}
                {formatPlaybackTime(selectedTrace.start_ms)}
              </p>
              {selectedTrace.broken ? (
                <p role="alert">
                  This evidence link no longer points to a saved transcript
                  turn.
                </p>
              ) : (
                <button
                  className="jump-button"
                  onClick={() => seekTo(selectedTrace.start_ms)}
                  type="button"
                >
                  Jump to matching audio
                </button>
              )}
            </>
          ) : (
            <>
              <p>
                Each factor contributes directly to the persisted Radar Priority
                score.
              </p>
              <ol className="evidence-candidates">
                {priority?.factors.map((factor) => (
                  <li key={factor.evidence_id}>
                    <button
                      onClick={() => openTrace("priority_factor", factor)}
                      type="button"
                    >
                      <strong>{factor.label}</strong>
                      <time>+{factor.contribution} points</time>
                      <span>Open transcript and audio evidence</span>
                    </button>
                  </li>
                ))}
              </ol>
            </>
          )}
        </aside>
      ) : null}
    </main>
  );
}
