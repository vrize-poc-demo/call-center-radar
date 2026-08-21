import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getCallDetail } from "../../api/calls";
import { CallDetailPage } from "./CallDetailPage";

vi.mock("../../api/calls", () => ({
  getCallDetail: vi.fn(),
  getCallAudioUrl: (callId: string) => `/api/calls/${callId}/audio`,
}));

const mockedGetCallDetail = vi.mocked(getCallDetail);

afterEach(() => {
  vi.resetAllMocks();
});

describe("CallDetailPage", () => {
  it("renders a clear loading state", () => {
    mockedGetCallDetail.mockReturnValue(new Promise(() => {}));

    render(<CallDetailPage callId="call-1" />);

    expect(screen.getByRole("heading", { name: "Loading call" })).toBeTruthy();
  });

  it("renders the primary call-detail regions after loading", async () => {
    mockedGetCallDetail.mockResolvedValue({
      call_id: "call-1",
      agent_name: "Agent One",
      customer_name: "Customer One",
      created_at: "2026-08-22 09:00:00",
      processing_status: "completed",
      audio_channels: 1,
      failure_reason: null,
      transcript_turn_count: 2,
    });

    render(<CallDetailPage callId="call-1" />);

    expect(
      await screen.findByRole("heading", { name: "Customer One" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "Call recording" }),
    ).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Transcript" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Evidence" })).toBeTruthy();
  });

  it("renders a readable missing-call state", async () => {
    mockedGetCallDetail.mockRejectedValue(new Error("Call not found."));

    render(<CallDetailPage callId="missing" />);

    expect(
      await screen.findByRole("heading", { name: "Call detail unavailable" }),
    ).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toBe("Call not found.");
  });
});
