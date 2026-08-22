import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  dismissProcessingQueueItem,
  getProcessingQueue,
} from "../../api/calls";
import { GlobalProcessingQueue } from "./GlobalProcessingQueue";

vi.mock("../../api/calls", () => ({
  dismissProcessingQueueItem: vi.fn(),
  getProcessingQueue: vi.fn(),
}));

const mockedGetProcessingQueue = vi.mocked(getProcessingQueue);
const mockedDismissProcessingQueueItem = vi.mocked(dismissProcessingQueueItem);

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.resetAllMocks();
});

describe("GlobalProcessingQueue", () => {
  it("shows a clear empty state after loading", async () => {
    mockedGetProcessingQueue.mockResolvedValue([]);

    render(<GlobalProcessingQueue />);

    expect(screen.getByText("Loading call status…")).toBeTruthy();
    expect(
      await screen.findByText(
        "No calls are processing or ready to review yet.",
      ),
    ).toBeTruthy();
  });

  it("renders status wording and open actions for completed and failed calls", async () => {
    mockedGetProcessingQueue.mockResolvedValue([
      {
        job_id: "job-active",
        call_id: "call-active",
        customer_name: "Ari Patel",
        status: "transcribing",
        updated_at: "2026-08-22 09:00:00",
        failure_reason: null,
      },
      {
        job_id: "job-ready",
        call_id: "call-ready",
        customer_name: "Nora Jones",
        status: "completed",
        updated_at: "2026-08-22 08:59:00",
        failure_reason: null,
      },
      {
        job_id: "job-failed",
        call_id: "call-failed",
        customer_name: "Sam Lee",
        status: "failed",
        updated_at: "2026-08-22 08:58:00",
        failure_reason: "invalid_audio",
      },
    ]);

    render(<GlobalProcessingQueue />);

    expect(await screen.findByText("Creating transcript")).toBeTruthy();
    expect(screen.getByText("Ready to review")).toBeTruthy();
    expect(screen.getByText("Needs attention")).toBeTruthy();
    expect(screen.getAllByRole("link", { name: "Open call" })).toHaveLength(2);
    expect(
      screen.getAllByRole("button", { name: "Remove from queue" }),
    ).toHaveLength(2);
    expect(screen.getByText("Ari Patel")).toBeTruthy();
  });

  it("removes a completed item after the safe queue-dismissal request succeeds", async () => {
    mockedGetProcessingQueue.mockResolvedValue([
      {
        job_id: "job-ready",
        call_id: "call-ready",
        customer_name: "Nora Jones",
        status: "completed",
        updated_at: "2026-08-22 08:59:00",
        failure_reason: null,
      },
    ]);
    mockedDismissProcessingQueueItem.mockResolvedValue();

    render(<GlobalProcessingQueue />);
    const remove = await screen.findByRole("button", {
      name: "Remove from queue",
    });
    fireEvent.click(remove);

    expect(mockedDismissProcessingQueueItem).toHaveBeenCalledWith("job-ready");
    expect(
      await screen.findByText(
        "No calls are processing or ready to review yet.",
      ),
    ).toBeTruthy();
  });

  it("keeps an item visible and shows recovery feedback when removal fails", async () => {
    mockedGetProcessingQueue.mockResolvedValue([
      {
        job_id: "job-failed",
        call_id: "call-failed",
        customer_name: "Sam Lee",
        status: "failed",
        updated_at: "2026-08-22 08:58:00",
        failure_reason: "invalid_audio",
      },
    ]);
    mockedDismissProcessingQueueItem.mockRejectedValue(new Error("offline"));
    const dismissalWarning = vi
      .spyOn(console, "warn")
      .mockImplementation(() => {});

    render(<GlobalProcessingQueue />);
    fireEvent.click(
      await screen.findByRole("button", { name: "Remove from queue" }),
    );

    expect(
      await screen.findByText(
        "The call could not be removed from the queue. Please try again.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("Sam Lee")).toBeTruthy();
    expect(dismissalWarning).toHaveBeenCalledWith(
      "processing_queue_dismiss_failed",
    );
  });

  it("refreshes status and makes a polling problem visible", async () => {
    const pollingWarning = vi
      .spyOn(console, "warn")
      .mockImplementation(() => {});
    vi.useFakeTimers();
    mockedGetProcessingQueue
      .mockResolvedValueOnce([])
      .mockRejectedValueOnce(new Error("offline"));

    render(<GlobalProcessingQueue />);
    await act(async () => {});
    expect(
      screen.getByText("No calls are processing or ready to review yet."),
    ).toBeTruthy();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });

    expect(screen.getByRole("status").textContent).toBe(
      "Queue status is temporarily unavailable.",
    );
    expect(pollingWarning).toHaveBeenCalledWith("processing_queue_poll_failed");
  });
});
