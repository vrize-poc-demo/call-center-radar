import { useEffect, useMemo, useState } from "react";

import { getDashboardTriage, TriageCall } from "../../api/calls";

function needsAttention(call: TriageCall) {
  return (
    call.risk_level === "high" ||
    call.analysis.resolution === "unresolved" ||
    call.analysis.false_resolution
  );
}

function riskLabel(call: TriageCall) {
  if (call.analysis.false_resolution) return "Resolution conflict";
  if (call.risk_level === "high") return "High risk";
  if (call.analysis.resolution === "unresolved") return "Needs follow-up";
  if (call.risk_level === "medium") return "Watch closely";
  return "Monitoring";
}

export function TodayDashboard() {
  const [calls, setCalls] = useState<TriageCall[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getDashboardTriage()
      .then((value) => {
        if (!active) return;
        setCalls(value);
        console.info("dashboard_loaded", { call_count: value.length });
      })
      .catch((reason: unknown) => {
        console.warn("dashboard_load_failed");
        if (active) {
          setError(
            reason instanceof Error
              ? reason.message
              : "Today's dashboard could not be loaded.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const summary = useMemo(() => {
    const items = calls ?? [];
    return {
      analyzed: items.length,
      highRisk: items.filter((call) => call.risk_level === "high").length,
      unresolved: items.filter(
        (call) => call.analysis.resolution === "unresolved",
      ).length,
      attention: items.filter(needsAttention).length,
      queue: items.filter(needsAttention).slice(0, 3),
      ranked: [...items].sort(
        (left, right) =>
          (right.radar_priority ?? -1) - (left.radar_priority ?? -1),
      ),
    };
  }, [calls]);

  if (error) {
    return (
      <main className="dashboard-shell">
        <p className="eyebrow">Manager dashboard</p>
        <h1>Today</h1>
        <p className="dashboard-error" role="alert">
          {error}
        </p>
        <a href="/">Register a call</a>
      </main>
    );
  }

  if (calls === null) {
    return (
      <main className="dashboard-shell" aria-busy="true">
        <p className="eyebrow">Manager dashboard</p>
        <h1>Today</h1>
        <p>Loading today’s risk signals…</p>
      </main>
    );
  }

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Manager dashboard</p>
          <h1>Today</h1>
          <p className="dashboard-subtitle">
            Start with the calls most likely to need action.
          </p>
        </div>
        <a className="secondary-link" href="/?register=true">
          Register a call
        </a>
        <a className="secondary-link" href="/?view=issues">
          Issue Radar
        </a>
      </header>

      <section className="kpi-grid" aria-label="Today’s call summary">
        <article className="kpi-card">
          <span>Needs attention</span>
          <strong>{summary.attention}</strong>
          <small>High risk, unresolved, or contradicted</small>
        </article>
        <article className="kpi-card kpi-high-risk">
          <span>High risk</span>
          <strong>{summary.highRisk}</strong>
          <small>Priority score of 60 or more</small>
        </article>
        <article className="kpi-card">
          <span>Unresolved</span>
          <strong>{summary.unresolved}</strong>
          <small>Customer outcome needs follow-up</small>
        </article>
        <article className="kpi-card">
          <span>Analyzed calls</span>
          <strong>{summary.analyzed}</strong>
          <small>Ready for manager triage</small>
        </article>
      </section>

      <section
        className="attention-panel"
        aria-labelledby="needs-attention-heading"
      >
        <div className="section-heading">
          <div>
            <p className="eyebrow">Act now</p>
            <h2 id="needs-attention-heading">Needs attention</h2>
          </div>
          <span>{summary.queue.length} shown</span>
        </div>
        {summary.queue.length === 0 ? (
          <div className="empty-dashboard-state">
            <h3>No urgent calls right now</h3>
            <p>
              Analyzed calls with high risk, an unresolved outcome, or a
              resolution contradiction will appear here.
            </p>
          </div>
        ) : (
          <ul className="attention-queue">
            {summary.queue.map((call) => (
              <li key={call.call_id}>
                <a href={`/?call=${call.call_id}`}>
                  <div>
                    <span className={`risk-badge risk-${call.risk_level}`}>
                      {riskLabel(call)}
                    </span>
                    <h3>{call.analysis.summary}</h3>
                    <p>{call.analysis.recommended_action}</p>
                  </div>
                  <span className="priority-summary">
                    Priority {call.radar_priority ?? "—"}
                  </span>
                </a>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section
        className="attention-panel"
        aria-labelledby="ranked-calls-heading"
      >
        <div className="section-heading">
          <div>
            <p className="eyebrow">Triage queue</p>
            <h2 id="ranked-calls-heading">All analyzed calls</h2>
          </div>
          <span>Highest priority first</span>
        </div>
        <ul className="attention-queue">
          {summary.ranked.map((call) => (
            <li key={call.call_id}>
              <a href={`/?call=${call.call_id}`}>
                <div>
                  <span className={`risk-badge risk-${call.risk_level}`}>
                    {riskLabel(call)}
                  </span>
                  <h3>{call.analysis.summary}</h3>
                  <p>
                    {call.analysis.resolution} · {call.analysis.mood}
                  </p>
                </div>
                <span className="priority-summary">
                  Priority {call.radar_priority ?? "—"}
                </span>
              </a>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
