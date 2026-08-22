import { useEffect, useState } from "react";

import { getProcessingQueue, ProcessingQueueItem } from "../../api/calls";

const POLL_INTERVAL_MS = 3_000;

const progressCopy: Record<ProcessingQueueItem["status"], string> = {
  queued: "Waiting to start",
  transcribing: "Creating transcript",
  analyzing: "Checking call details",
  completed: "Ready to review",
  failed: "Needs attention",
};

function refreshQueue(
  setItems: (items: ProcessingQueueItem[]) => void,
  setError: (error: string | null) => void,
) {
  return getProcessingQueue()
    .then((items) => {
      setItems(items);
      setError(null);
    })
    .catch(() => {
      console.warn("processing_queue_poll_failed");
      setError("Queue status is temporarily unavailable.");
    });
}

export function GlobalProcessingQueue() {
  const [items, setItems] = useState<ProcessingQueueItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void refreshQueue(setItems, setError);
    const interval = window.setInterval(() => {
      void refreshQueue(setItems, setError);
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, []);

  return (
    <section aria-label="Call processing" className="global-processing-queue">
      <div className="queue-heading">
        <div>
          <p className="eyebrow">Call processing</p>
          <h2>Recent calls</h2>
        </div>
        {items ? <span>{items.length} recent</span> : null}
      </div>
      {error ? <p role="status">{error}</p> : null}
      {items === null ? <p aria-busy="true">Loading call status…</p> : null}
      {items?.length === 0 ? (
        <p>No calls are processing or ready to review yet.</p>
      ) : null}
      {items?.length ? (
        <ol className="processing-queue-items">
          {items.map((item) => (
            <li key={item.job_id}>
              <div>
                <strong>{item.customer_name}</strong>
                <span>{progressCopy[item.status]}</span>
              </div>
              <span className={`status-badge status-${item.status}`}>
                {item.status}
              </span>
              {item.status === "completed" || item.status === "failed" ? (
                <a href={`?call=${item.call_id}`}>Open call</a>
              ) : null}
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
