import { type ReactNode } from "react";

import { CallUploadForm } from "./features/calls/CallUploadForm";
import { CallDetailPage } from "./features/call-detail/CallDetailPage";
import { TodayDashboard } from "./features/dashboard/TodayDashboard";
import { IssueRadar } from "./features/issue-radar/IssueRadar";
import { AgentSummaryPage } from "./features/agents/AgentSummaryPage";
import { CustomerJourney } from "./features/customer-journey/CustomerJourney";
import { ServiceHealthStatusBar } from "./features/health/ServiceHealthStatusBar";
import { GlobalProcessingQueue } from "./features/processing/GlobalProcessingQueue";

function AppTopNav() {
  return (
    <nav className="app-top-nav" aria-label="Primary">
      <a className="app-home-link" href="/">
        <span className="app-home-mark">⌂</span>
        <span>Call Center Radar</span>
      </a>
      <div className="app-top-nav-links">
        <a href="/">Home</a>
        <a href="/?register=true">Register</a>
        <a href="/?view=issues">Issues</a>
        <a href="/?view=agents">Agents</a>
      </div>
    </nav>
  );
}

function AppContent({ children }: { children: ReactNode }) {
  return (
    <div className="app-workspace-content">
      <AppTopNav />
      {children}
      <ServiceHealthStatusBar />
    </div>
  );
}

export function App() {
  const callId = new URLSearchParams(window.location.search).get("call");
  const view = new URLSearchParams(window.location.search).get("view");
  if (callId)
    return (
      <div className="app-workspace">
        <GlobalProcessingQueue />
        <AppContent>
          <CallDetailPage callId={callId} />
        </AppContent>
      </div>
    );
  if (!new URLSearchParams(window.location.search).has("register")) {
    return (
      <div className="app-workspace">
        <GlobalProcessingQueue />
        <AppContent>
          {view === "issues" ? (
            <IssueRadar />
          ) : view === "agents" ? (
            <AgentSummaryPage />
          ) : view === "journey" ? (
            <CustomerJourney />
          ) : (
            <TodayDashboard />
          )}
        </AppContent>
      </div>
    );
  }

  return (
    <div className="app-workspace">
      <GlobalProcessingQueue />
      <AppContent>
        <main className="app-shell">
          <p className="eyebrow">Call Center Radar</p>
          <h1>Evidence-first call intelligence</h1>
          <p>
            Give managers an evidence-backed queue of calls that need attention.
          </p>
          <CallUploadForm />
        </main>
      </AppContent>
    </div>
  );
}
