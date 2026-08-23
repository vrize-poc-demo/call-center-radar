import { useEffect, useMemo, useState } from "react";

import {
  getDashboardTriage,
  getIssueRadar,
  IssueCategory,
  TriageCall,
} from "../../api/calls";

function needsAttention(call: TriageCall | undefined) {
  return (
    call?.risk_level === "high" ||
    call?.analysis.resolution === "unresolved" ||
    call?.analysis.false_resolution === true
  );
}

function trendLabel(category: IssueCategory) {
  if (category.trend === "not_enough_data") return "Needs more data";
  return category.trend[0].toUpperCase() + category.trend.slice(1);
}

export function IssueRadar() {
  const [categories, setCategories] = useState<IssueCategory[] | null>(null);
  const [triageCalls, setTriageCalls] = useState<TriageCall[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([getIssueRadar(), getDashboardTriage()])
      .then(([issueGroups, triage]) => {
        if (!active) return;
        setCategories(issueGroups);
        setTriageCalls(triage);
        console.info("issue_radar_loaded", {
          category_count: issueGroups.length,
        });
      })
      .catch((reason: unknown) => {
        console.warn("issue_radar_load_failed");
        if (active) {
          setError(
            reason instanceof Error
              ? reason.message
              : "Issue Radar could not be loaded.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const callsById = useMemo(
    () => new Map(triageCalls.map((call) => [call.call_id, call])),
    [triageCalls],
  );

  if (error) {
    return (
      <main className="dashboard-shell">
        <p className="eyebrow">Manager dashboard</p>
        <h1>Issue Radar</h1>
        <p className="dashboard-error" role="alert">
          {error}
        </p>
        <a href="/">Back to Today</a>
      </main>
    );
  }

  if (categories === null) {
    return (
      <main className="dashboard-shell" aria-busy="true">
        <p className="eyebrow">Manager dashboard</p>
        <h1>Issue Radar</h1>
        <p>Loading recurring issue signals…</p>
      </main>
    );
  }

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Manager dashboard</p>
          <h1>Issue Radar</h1>
          <p className="dashboard-subtitle">
            Recurring customer issues, grouped from analyzed calls.
          </p>
        </div>
        <a className="secondary-link" href="/">
          Back to Today
        </a>
      </header>

      {categories.length === 0 ? (
        <section className="attention-panel empty-dashboard-state">
          <h2>No recurring issues yet</h2>
          <p>Issue groups appear after calls have been analyzed.</p>
        </section>
      ) : (
        <section
          className="issue-radar-grid"
          aria-label="Recurring issue groups"
        >
          {categories.map((category) => {
            const representative = callsById.get(
              category.representative_call_id,
            );
            const critical = needsAttention(representative);
            const relatedCallIds = category.related_call_ids.filter(
              (callId) => callId !== category.representative_call_id,
            );
            return (
              <article className="issue-card" key={category.key}>
                <div className="issue-card-heading">
                  <div>
                    <p className="eyebrow">
                      {category.call_count} related calls
                    </p>
                    <h2>{category.label}</h2>
                  </div>
                  <div className="issue-labels">
                    {critical && (
                      <span className="issue-label issue-critical">
                        Critical
                      </span>
                    )}
                    <span className={`issue-label issue-${category.trend}`}>
                      {trendLabel(category)}
                    </span>
                  </div>
                </div>
                <p className="issue-trend-copy">
                  {category.current_window_count} in the last 7 days ·{" "}
                  {category.previous_window_count} in the previous 7 days
                </p>
                <a
                  className="issue-primary-action"
                  href={`/?call=${category.representative_call_id}`}
                  onClick={() =>
                    console.info("issue_radar_representative_opened", {
                      issue_key: category.key,
                    })
                  }
                >
                  Inspect representative call
                </a>
                {relatedCallIds.length > 0 && (
                  <details className="related-calls">
                    <summary>
                      Open related calls ({relatedCallIds.length})
                    </summary>
                    <ul>
                      {relatedCallIds.map((callId) => (
                        <li key={callId}>
                          <a href={`/?call=${callId}`}>Open related call</a>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </article>
            );
          })}
        </section>
      )}
    </main>
  );
}
