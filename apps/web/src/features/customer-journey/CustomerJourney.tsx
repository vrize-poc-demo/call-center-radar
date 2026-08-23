import { useEffect, useState } from "react";
import { CustomerHistoryCall, getCustomerHistory } from "../../api/calls";

export function CustomerJourney() {
  const callId = new URLSearchParams(window.location.search).get("journeyCall");
  const [calls, setCalls] = useState<CustomerHistoryCall[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!callId) {
      setError("Open Customer Journey from a call detail page.");
      return;
    }
    getCustomerHistory(callId)
      .then((value) => {
        setCalls(value);
        console.info("customer_journey_loaded", { call_count: value.length });
      })
      .catch((reason: unknown) => {
        console.warn("customer_journey_load_failed");
        setError(
          reason instanceof Error
            ? reason.message
            : "Customer history could not be loaded.",
        );
      });
  }, [callId]);
  if (error)
    return (
      <main className="dashboard-shell">
        <h1>Customer Journey</h1>
        <p role="alert" className="dashboard-error">
          {error}
        </p>
        <a href="/">Back to Today</a>
      </main>
    );
  if (calls === null)
    return (
      <main className="dashboard-shell" aria-busy="true">
        <h1>Customer Journey</h1>
        <p>Loading customer history…</p>
      </main>
    );
  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Customer Journey</p>
          <h1>Contact history</h1>
          <p className="dashboard-subtitle">
            A chronological view of outcomes and repeat issues.
          </p>
        </div>
        <a className="secondary-link" href="/">
          Back to Today
        </a>
      </header>
      <ol className="journey-timeline">
        {calls.map((call) => (
          <li key={call.call_id}>
            <article>
              <time>{call.created_at}</time>
              <strong>
                {call.analysis_status === "analyzed"
                  ? `${call.mood} · ${call.resolution}`
                  : "Not analyzed"}
              </strong>
              {call.issue && (
                <span className="issue-label">
                  {call.issue.repeated
                    ? `Repeated: ${call.issue.label}`
                    : call.issue.label}
                </span>
              )}
              <a href={`/?call=${call.call_id}`}>Open call</a>
            </article>
          </li>
        ))}
      </ol>
    </main>
  );
}
