import { CallUploadForm } from "./features/calls/CallUploadForm";
import { CallDetailPage } from "./features/call-detail/CallDetailPage";

export function App() {
  const callId = new URLSearchParams(window.location.search).get("call");
  if (callId) return <CallDetailPage callId={callId} />;

  return (
    <main className="app-shell">
      <p className="eyebrow">Call Center Radar</p>
      <h1>Evidence-first call intelligence</h1>
      <p>
        Give managers an evidence-backed queue of calls that need attention.
      </p>
      <CallUploadForm />
    </main>
  );
}
