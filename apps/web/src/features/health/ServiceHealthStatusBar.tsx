import { useEffect, useState } from "react";

import {
  getServiceHealth,
  type ServiceHealthCheck,
  type ServiceHealthReport,
  type ServiceStatus,
} from "../../api/calls";

const POLL_INTERVAL_MS = 10_000;

const statusCopy: Record<ServiceStatus, string> = {
  healthy: "Healthy",
  degraded: "Needs setup",
  unhealthy: "Not healthy",
};

function serviceSummary(services: ServiceHealthCheck[] | null): string {
  if (!services) return "Checking services";
  const failed = services.filter((service) => service.status === "unhealthy");
  const degraded = services.filter((service) => service.status === "degraded");
  if (failed.length) return `${failed.length} service needs attention`;
  if (degraded.length) return `${degraded.length} service needs setup`;
  return "All services running";
}

export function ServiceHealthStatusBar() {
  const [report, setReport] = useState<ServiceHealthReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const overallStatus = error ? "unhealthy" : (report?.status ?? "degraded");

  useEffect(() => {
    let isMounted = true;

    function refreshHealth() {
      void getServiceHealth()
        .then((nextReport) => {
          if (!isMounted) return;
          setReport(nextReport);
          setError(null);
        })
        .catch(() => {
          if (!isMounted) return;
          console.warn("service_health_poll_failed");
          setError("API is not reachable. Start the backend and refresh.");
        });
    }

    refreshHealth();
    const interval = window.setInterval(refreshHealth, POLL_INTERVAL_MS);
    return () => {
      isMounted = false;
      window.clearInterval(interval);
    };
  }, []);

  return (
    <section className="service-health-shell" aria-label="System health">
      <button
        aria-expanded={isExpanded}
        className={`service-health-bar service-health-${overallStatus}`}
        onClick={() => setIsExpanded((current) => !current)}
        type="button"
      >
        <span className="service-health-dot" aria-hidden="true" />
        <strong>{statusCopy[overallStatus]}</strong>
        <span>{error ?? serviceSummary(report?.services ?? null)}</span>
        <span className="service-health-toggle">
          {isExpanded ? "Hide" : "Details"}
        </span>
      </button>

      {isExpanded ? (
        <div className="service-health-panel">
          <div className="service-health-panel-heading">
            <h2>Service Health</h2>
            <p>
              Confirm the app, data, processing, transcription, and local LLM
              stack before a demo.
            </p>
          </div>
          {error ? <p role="status">{error}</p> : null}
          {!error && !report ? (
            <p role="status" aria-busy="true">
              Checking services…
            </p>
          ) : null}
          {report ? (
            <ul className="service-health-list">
              {report.services.map((service) => (
                <li key={service.key}>
                  <div>
                    <span
                      className={`service-health-mini-dot service-health-mini-${service.status}`}
                      aria-hidden="true"
                    />
                    <strong>{service.label}</strong>
                    <span>{statusCopy[service.status]}</span>
                  </div>
                  <p>{service.detail}</p>
                  {service.action_hint ? (
                    <div className="service-health-action">
                      <span>{service.action_label ?? "Action"}</span>
                      <code>{service.action_hint}</code>
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
