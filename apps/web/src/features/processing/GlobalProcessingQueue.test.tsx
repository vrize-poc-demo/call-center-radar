import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getProcessingQueue } from "../../api/calls";
import { GlobalProcessingQueue } from "./GlobalProcessingQueue";

vi.mock("../../api/calls", () => ({
  getProcessingQueue: vi.fn(),
}));

const mockedGetProcessingQueue = vi.mocked(getProcessingQueue);

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
    expect(screen.getByText("Ari Patel")).toBeTruthy();
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
