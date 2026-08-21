import { CallUploadForm } from "./features/calls/CallUploadForm";

export function App() {
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
