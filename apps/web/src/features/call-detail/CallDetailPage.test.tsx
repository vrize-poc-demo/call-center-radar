import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getCallDetail, getTranscript } from "../../api/calls";
import { CallDetailPage } from "./CallDetailPage";

vi.mock("../../api/calls", () => ({
  getCallDetail: vi.fn(),
  getTranscript: vi.fn(),
  getCallAudioUrl: (callId: string) => `/api/calls/${callId}/audio`,
}));

const mockedGetCallDetail = vi.mocked(getCallDetail);
const mockedGetTranscript = vi.mocked(getTranscript);

afterEach(() => {
  vi.resetAllMocks();
});

describe("CallDetailPage", () => {
  it("renders a clear loading state", () => {
    mockedGetCallDetail.mockReturnValue(new Promise(() => {}));
    mockedGetTranscript.mockResolvedValue([]);

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
    mockedGetTranscript.mockResolvedValue([
      {
        transcript_turn_id: "turn-1",
        speaker: "agent",
        start_ms: 0,
        end_ms: 1000,
        text: "Welcome",
      },
    ]);

    render(<CallDetailPage callId="call-1" />);

    expect(
      await screen.findByRole("heading", { name: "Customer One" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "Call recording" }),
    ).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Transcript" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Evidence" })).toBeTruthy();
    expect(screen.getByText("Welcome")).toBeTruthy();
  });

  it("renders a readable missing-call state", async () => {
    mockedGetCallDetail.mockRejectedValue(new Error("Call not found."));
    mockedGetTranscript.mockResolvedValue([]);

    render(<CallDetailPage callId="missing" />);

    expect(
      await screen.findByRole("heading", { name: "Call detail unavailable" }),
    ).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toBe("Call not found.");
  });

  it("shows the current timestamp reported by the audio player", async () => {
    mockedGetCallDetail.mockResolvedValue({
      call_id: "call-1",
      agent_name: "Agent",
      customer_name: "Customer",
      created_at: "2026-08-22",
      processing_status: "completed",
      audio_channels: 1,
      failure_reason: null,
      transcript_turn_count: 0,
    });
    mockedGetTranscript.mockResolvedValue([]);

    render(<CallDetailPage callId="call-1" />);
    await screen.findByRole("heading", { name: "Call recording" });
    const audio = document.querySelector("audio") as HTMLAudioElement;
    Object.defineProperty(audio, "currentTime", {
      configurable: true,
      get: () => 65,
    });

    fireEvent.timeUpdate(audio);

    expect(screen.getByText("Playback position: 1:05")).toBeTruthy();
  });

  it("highlights and seeks the active transcript turn", async () => {
    mockedGetCallDetail.mockResolvedValue({
      call_id: "call-1",
      agent_name: "Agent",
      customer_name: "Customer",
      created_at: "2026-08-22",
      processing_status: "completed",
      audio_channels: 1,
      failure_reason: null,
      transcript_turn_count: 1,
    });
    mockedGetTranscript.mockResolvedValue([
      {
        transcript_turn_id: "turn-1",
        speaker: "agent",
        start_ms: 500,
        end_ms: 1500,
        text: "Synced turn",
      },
    ]);
    const { container } = render(<CallDetailPage callId="call-1" />);
    await screen.findByText("Synced turn");
    const currentTimeSetter = vi.spyOn(
      HTMLMediaElement.prototype,
      "currentTime",
      "set",
    );
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();

    fireEvent.click(screen.getByText("Synced turn"));

    await waitFor(() =>
      expect(screen.getByText("Synced turn").closest("li")?.className).toBe(
        "active-turn",
      ),
    );
    expect(currentTimeSetter).toHaveBeenCalledWith(0.5);

    fireEvent.click(
      within(container).getByRole("button", { name: "Jump to call start" }),
    );

    expect(currentTimeSetter).toHaveBeenLastCalledWith(0);
  });
});
