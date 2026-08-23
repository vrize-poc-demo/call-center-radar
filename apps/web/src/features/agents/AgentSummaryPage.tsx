import { useEffect, useMemo, useState } from "react";

import { AgentSummary, getAgentSummaries } from "../../api/calls";

function supportLabel(agent: AgentSummary) {
  if (agent.treatment_signal_count > 0) return "Support check";
  if (agent.false_resolution_count > 0) return "Resolution coaching";
  if (agent.unresolved_count > 0) return "Follow-up coaching";
  if (agent.difficult_calls > 0) return "Monitor mix";
  return "Stable";
}

function formatDuration(milliseconds: number | null) {
  if (milliseconds === null) return "—";
  const totalSeconds = Math.round(milliseconds / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function AgentSummaryPage() {
  const [agents, setAgents] = useState<AgentSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getAgentSummaries()
      .then((value) => {
        if (!active) return;
        setAgents(value);
        console.info("agent_summary_loaded", { agent_count: value.length });
      })
      .catch((reason: unknown) => {
        console.warn("agent_summary_load_failed");
        if (active) {
          setError(
            reason instanceof Error
              ? reason.message
              : "Agent summaries could not be loaded.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const totals = useMemo(() => {
    const items = agents ?? [];
    const callsHandled = items.reduce(
      (total, agent) => total + agent.calls_handled,
      0,
    );
    const difficultCalls = items.reduce(
      (total, agent) => total + agent.difficult_calls,
      0,
    );
    const resolvedCalls = items.reduce(
      (total, agent) => total + agent.resolved_count,
      0,
    );
    const handleTimeAgents = items.filter(
      (agent) => agent.average_handle_time_ms !== null,
    );
    const averageHandleTime =
      handleTimeAgents.length === 0
        ? null
        : Math.round(
            handleTimeAgents.reduce(
              (total, agent) => total + (agent.average_handle_time_ms ?? 0),
              0,
            ) / handleTimeAgents.length,
          );
    const estimatedSatisfaction =
      items.length === 0
        ? 0
        : Math.round(
            items.reduce(
              (total, agent) => total + agent.estimated_satisfaction,
              0,
            ) / items.length,
          );
    return {
      agents: items.length,
      callsHandled,
      difficultCalls,
      resolvedCalls,
      averageHandleTime,
      estimatedSatisfaction,
    };
  }, [agents]);

  if (error) {
    return (
      <main className="dashboard-shell">
        <p className="eyebrow">Manager dashboard</p>
        <h1>Agent support</h1>
        <p className="dashboard-error" role="alert">
          {error}
        </p>
        <a href="/">Back to Today</a>
      </main>
    );
  }

  if (agents === null) {
    return (
      <main className="dashboard-shell" aria-busy="true">
        <p className="eyebrow">Manager dashboard</p>
        <h1>Agent support</h1>
        <p>Loading agent support patterns...</p>
      </main>
    );
  }

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Manager dashboard</p>
          <h1>Agent support</h1>
          <p className="dashboard-subtitle">
            Supportive coaching view built from analyzed call outcomes and
            evidence-backed difficult interaction signals.
          </p>
        </div>
        <a className="secondary-link" href="/">
          Back to Today
        </a>
      </header>

      <section className="kpi-grid" aria-label="Agent support summary">
        <article className="kpi-card">
          <span>Agents</span>
          <strong>{totals.agents}</strong>
          <small>With analyzed calls</small>
        </article>
        <article className="kpi-card">
          <span>Calls handled</span>
          <strong>{totals.callsHandled}</strong>
          <small>Analyzed interactions</small>
        </article>
        <article className="kpi-card kpi-high-risk">
          <span>Difficult calls</span>
          <strong>{totals.difficultCalls}</strong>
          <small>High risk, unresolved, conflict, or treatment signal</small>
        </article>
        <article className="kpi-card">
          <span>Avg handle time</span>
          <strong>{formatDuration(totals.averageHandleTime)}</strong>
          <small>From saved call or transcript timing</small>
        </article>
        <article className="kpi-card">
          <span>Resolved calls</span>
          <strong>{totals.resolvedCalls}</strong>
          <small>Analyzed calls marked resolved</small>
        </article>
        <article className="kpi-card">
          <span>Estimated satisfaction</span>
          <strong>{totals.estimatedSatisfaction}</strong>
          <small>Outcome and mood based estimate</small>
        </article>
      </section>

      {agents.length === 0 ? (
        <section className="attention-panel empty-dashboard-state">
          <h2>No agent patterns yet</h2>
          <p>Agent summaries appear after calls have persisted analysis.</p>
        </section>
      ) : (
        <section className="agent-summary-grid" aria-label="Agent summaries">
          {agents.map((agent) => (
            <article className="agent-summary-card" key={agent.agent_name}>
              <div className="agent-card-heading">
                <div>
                  <p className="eyebrow">{supportLabel(agent)}</p>
                  <h2>{agent.agent_name}</h2>
                </div>
                <span>{agent.estimated_satisfaction}/100</span>
              </div>
              <dl className="agent-metrics">
                <div>
                  <dt>Calls handled</dt>
                  <dd>{agent.calls_handled}</dd>
                </div>
                <div>
                  <dt>Difficult calls</dt>
                  <dd>{agent.difficult_calls}</dd>
                </div>
                <div>
                  <dt>Avg handle time</dt>
                  <dd>{formatDuration(agent.average_handle_time_ms)}</dd>
                </div>
                <div>
                  <dt>Resolved</dt>
                  <dd>
                    {agent.resolved_count} ({agent.resolved_rate}%)
                  </dd>
                </div>
                <div>
                  <dt>Avg priority</dt>
                  <dd>{agent.average_priority ?? "—"}</dd>
                </div>
                <div>
                  <dt>Treatment signals</dt>
                  <dd>{agent.treatment_signal_count}</dd>
                </div>
                <div>
                  <dt>Unresolved</dt>
                  <dd>{agent.unresolved_count}</dd>
                </div>
              </dl>
              <p className="supporting-copy">{agent.coaching_note}</p>
              {agent.recent_call_ids.length > 0 && (
                <div className="recent-call-links">
                  {agent.recent_call_ids.map((callId) => (
                    <a href={`/?call=${callId}`} key={callId}>
                      Open recent call
                    </a>
                  ))}
                </div>
              )}
            </article>
          ))}
        </section>
      )}
    </main>
  );
}
