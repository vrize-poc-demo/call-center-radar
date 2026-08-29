import { useEffect, useState } from "react";

import {
  clearAllCallData,
  dismissProcessingQueueItem,
  getProcessingQueue,
  ProcessingQueueItem,
} from "../../api/calls";

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
  const [dismissingJobId, setDismissingJobId] = useState<string | null>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isResetOpen, setIsResetOpen] = useState(false);
  const [resetConfirmation, setResetConfirmation] = useState("");
  const [isClearing, setIsClearing] = useState(false);
  const [resetMessage, setResetMessage] = useState<string | null>(null);
  const itemCount = items?.length ?? 0;
  const itemCountLabel =
    items === null
      ? "Loading"
      : `${itemCount} ${itemCount === 1 ? "call" : "calls"}`;

  useEffect(() => {
    void refreshQueue(setItems, setError);
    const interval = window.setInterval(() => {
      void refreshQueue(setItems, setError);
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, []);

  async function dismissItem(item: ProcessingQueueItem) {
    setDismissingJobId(item.job_id);
    setError(null);
    try {
      await dismissProcessingQueueItem(item.job_id);
      setItems(
        (currentItems) =>
          currentItems?.filter(
            (currentItem) => currentItem.job_id !== item.job_id,
          ) ?? null,
      );
    } catch {
      console.warn("processing_queue_dismiss_failed");
      setError(
        "The call could not be removed from the queue. Please try again.",
      );
    } finally {
      setDismissingJobId(null);
    }
  }

  function logOpenDetail(item: ProcessingQueueItem) {
    console.info("queue_to_detail_requested", { call_id: item.call_id });
  }

  async function clearDemoData() {
    setIsClearing(true);
    setResetMessage(null);
    setError(null);
    try {
      const cleared = await clearAllCallData();
      setItems([]);
      setResetConfirmation("");
      setResetMessage(
        `Cleared ${cleared.calls_deleted} stored call${cleared.calls_deleted === 1 ? "" : "s"} and removed ${cleared.upload_files_deleted} uploaded file${cleared.upload_files_deleted === 1 ? "" : "s"}.`,
      );
    } catch {
      console.warn("demo_reset_failed");
      setResetMessage("Demo data could not be cleared. Please try again.");
    } finally {
      setIsClearing(false);
    }
  }

  const resetDialog = isResetOpen ? (
    <div className="queue-reset-backdrop" role="presentation">
      <section
        aria-labelledby="queue-reset-title"
        aria-modal="true"
        className="queue-reset-dialog"
        role="dialog"
      >
        <h2 id="queue-reset-title">Clear demo data</h2>
        <p>
          This removes saved calls, transcripts, analysis, queue history, and
          uploaded files from this local POC.
        </p>
        <label>
          Type DELETE to confirm
          <input
            autoFocus
            onChange={(event) =>
              setResetConfirmation(event.currentTarget.value)
            }
            value={resetConfirmation}
          />
        </label>
        {resetMessage ? <p role="status">{resetMessage}</p> : null}
        <div className="queue-reset-actions">
          <button
            className="clear-data-button"
            disabled={isClearing || resetConfirmation !== "DELETE"}
            onClick={() => void clearDemoData()}
            type="button"
          >
            {isClearing ? "Clearing…" : "Clear all data"}
          </button>
          <button
            onClick={() => {
              setIsResetOpen(false);
              setResetConfirmation("");
              setResetMessage(null);
            }}
            type="button"
          >
            Cancel
          </button>
        </div>
      </section>
    </div>
  ) : null;

  if (isCollapsed) {
    return (
      <section
        aria-label="Call processing"
        className="global-processing-queue global-processing-queue-collapsed"
      >
        <div className="queue-collapsed-top">
          <span className="queue-collapsed-count">{itemCountLabel}</span>
          <button
            aria-expanded="false"
            aria-label="Expand recent calls"
            className="queue-side-tab"
            onClick={() => setIsCollapsed(false)}
            type="button"
          >
            &gt;
          </button>
        </div>
        <button
          aria-label="Open demo reset settings"
          className="queue-settings-button"
          onClick={() => setIsResetOpen(true)}
          title="Demo reset"
          type="button"
        >
          ⚙
        </button>
        {resetDialog}
      </section>
    );
  }

  return (
    <section aria-label="Call processing" className="global-processing-queue">
      <div className="queue-heading">
        <div>
          <p className="eyebrow">Call processing</p>
          <h2>Recent calls</h2>
        </div>
        <div className="queue-heading-actions">
          {items ? <span>{items.length} recent</span> : null}
          <button
            aria-expanded="true"
            onClick={() => setIsCollapsed(true)}
            type="button"
          >
            Hide panel
          </button>
        </div>
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
              {item.status === "completed" ? (
                <div className="queue-actions">
                  <a
                    href={`?call=${item.call_id}`}
                    onClick={() => logOpenDetail(item)}
                  >
                    Open call detail
                  </a>
                  <button
                    disabled={dismissingJobId === item.job_id}
                    onClick={() => void dismissItem(item)}
                    type="button"
                  >
                    {dismissingJobId === item.job_id
                      ? "Removing…"
                      : "Remove from queue"}
                  </button>
                </div>
              ) : item.status === "failed" ? (
                <div className="queue-actions">
                  <span className="queue-failure-note">
                    Processing stopped. Upload a corrected recording to try
                    again.
                  </span>
                  <button
                    disabled={dismissingJobId === item.job_id}
                    onClick={() => void dismissItem(item)}
                    type="button"
                  >
                    {dismissingJobId === item.job_id
                      ? "Removing…"
                      : "Remove from queue"}
                  </button>
                </div>
              ) : null}
            </li>
          ))}
        </ol>
      ) : null}
      {resetDialog}
    </section>
  );
}
