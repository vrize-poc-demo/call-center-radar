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

  it("offers persisted detail navigation only for completed calls", async () => {
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
    const detailLink = screen.getByRole("link", { name: "Open call detail" });
    detailLink.addEventListener("click", (event) => event.preventDefault());
    expect(detailLink.getAttribute("href")).toBe("?call=call-ready");
    const navigationLog = vi
      .spyOn(console, "info")
      .mockImplementation(() => {});
    fireEvent.click(detailLink);
    expect(navigationLog).toHaveBeenCalledWith("queue_to_detail_requested", {
      call_id: "call-ready",
    });
    expect(
      screen.getAllByRole("link", { name: "Open call detail" }),
    ).toHaveLength(1);
    expect(
      screen.getByText(
        "Processing stopped. Upload a corrected recording to try again.",
      ),
    ).toBeTruthy();
    expect(
      screen.getAllByRole("button", { name: "Remove from queue" }),
    ).toHaveLength(2);
    expect(screen.getByText("Ari Patel")).toBeTruthy();
  });

  it("collapses to a side tab and expands without losing recent calls", async () => {
    mockedGetProcessingQueue.mockResolvedValue([
      {
        job_id: "job-ready",
        call_id: "call-ready",
        customer_name: "Nora Jones",
        status: "completed",
        updated_at: "2026-08-22 08:59:00",
        failure_reason: null,
      },
      {
        job_id: "job-active",
        call_id: "call-active",
        customer_name: "Ari Patel",
        status: "transcribing",
        updated_at: "2026-08-22 09:00:00",
        failure_reason: null,
      },
    ]);

    render(<GlobalProcessingQueue />);

    expect(await screen.findByText("Nora Jones")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Hide panel" }));

    const expandTab = screen.getByRole("button", {
      name: /Call processing Recent calls 2 calls/,
    });
    expect(expandTab.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("Nora Jones")).toBeNull();

    fireEvent.click(expandTab);

    expect(screen.getByRole("button", { name: "Hide panel" })).toBeTruthy();
    expect(screen.getByText("Nora Jones")).toBeTruthy();
    expect(screen.getByText("Ari Patel")).toBeTruthy();
  });

  it("keeps polling while the recent-calls panel is collapsed", async () => {
    vi.useFakeTimers();
    mockedGetProcessingQueue
      .mockResolvedValueOnce([
        {
          job_id: "job-active",
          call_id: "call-active",
          customer_name: "Ari Patel",
          status: "transcribing",
          updated_at: "2026-08-22 09:00:00",
          failure_reason: null,
        },
      ])
      .mockResolvedValueOnce([
        {
          job_id: "job-ready",
          call_id: "call-ready",
          customer_name: "Nora Jones",
          status: "completed",
          updated_at: "2026-08-22 09:01:00",
          failure_reason: null,
        },
        {
          job_id: "job-active",
          call_id: "call-active",
          customer_name: "Ari Patel",
          status: "transcribing",
          updated_at: "2026-08-22 09:00:00",
          failure_reason: null,
        },
      ]);

    render(<GlobalProcessingQueue />);
    await act(async () => {});
    expect(screen.getByText("Ari Patel")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Hide panel" }));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });

    expect(
      screen.getByRole("button", {
        name: /Call processing Recent calls 2 calls/,
      }),
    ).toBeTruthy();

    fireEvent.click(
      screen.getByRole("button", {
        name: /Call processing Recent calls 2 calls/,
      }),
    );

    expect(screen.getByText("Nora Jones")).toBeTruthy();
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
