import { CallUploadForm } from "./features/calls/CallUploadForm";
import { CallDetailPage } from "./features/call-detail/CallDetailPage";
import { TodayDashboard } from "./features/dashboard/TodayDashboard";
import { IssueRadar } from "./features/issue-radar/IssueRadar";
import { AgentSummaryPage } from "./features/agents/AgentSummaryPage";
import { CustomerJourney } from "./features/customer-journey/CustomerJourney";
import { GlobalProcessingQueue } from "./features/processing/GlobalProcessingQueue";

export function App() {
  const callId = new URLSearchParams(window.location.search).get("call");
  const view = new URLSearchParams(window.location.search).get("view");
  if (callId)
    return (
      <div className="app-workspace">
        <GlobalProcessingQueue />
        <div className="app-workspace-content">
          <CallDetailPage callId={callId} />
        </div>
      </div>
    );
  if (!new URLSearchParams(window.location.search).has("register")) {
    return (
      <div className="app-workspace">
        <GlobalProcessingQueue />
        <div className="app-workspace-content">
          {view === "issues" ? (
            <IssueRadar />
          ) : view === "agents" ? (
            <AgentSummaryPage />
          ) : view === "journey" ? (
            <CustomerJourney />
          ) : (
            <TodayDashboard />
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="app-workspace">
      <GlobalProcessingQueue />
      <div className="app-workspace-content">
        <main className="app-shell">
          <p className="eyebrow">Call Center Radar</p>
          <h1>Evidence-first call intelligence</h1>
          <p>
            Give managers an evidence-backed queue of calls that need attention.
          </p>
          <CallUploadForm />
        </main>
      </div>
    </div>
  );
}
