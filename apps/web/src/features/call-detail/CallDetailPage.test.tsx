import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  calculatePriority,
  getAnalysis,
  getCallDetail,
  getEvidence,
  getTranscript,
} from "../../api/calls";
import { CallDetailPage } from "./CallDetailPage";

vi.mock("../../api/calls", () => ({
  getCallDetail: vi.fn(),
  getEvidence: vi.fn(),
  getTranscript: vi.fn(),
  calculatePriority: vi.fn(),
  getAnalysis: vi.fn(),
  getCallAudioUrl: (callId: string) => `/api/calls/${callId}/audio`,
}));

const mockedGetCallDetail = vi.mocked(getCallDetail);
const mockedGetTranscript = vi.mocked(getTranscript);
const mockedGetEvidence = vi.mocked(getEvidence);
const mockedCalculatePriority = vi.mocked(calculatePriority);
const mockedGetAnalysis = vi.mocked(getAnalysis);

beforeEach(() => {
  mockedGetEvidence.mockResolvedValue([]);
  mockedCalculatePriority.mockResolvedValue({
    call_id: "call-1",
    score: 0,
    scoring_version: "radar-priority-v1",
    factors: [],
  });
  mockedGetAnalysis.mockResolvedValue({
    intent: "Support",
    mood: "negative",
    resolution: "unresolved",
    summary: "Summary",
    manager_brief: "Review the support concern.",
    recommended_action: "Follow up.",
    claims: [],
    model_version: "test-v1",
  });
});

afterEach(() => {
  cleanup();
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

  it("shows deterministic evidence and jumps to its saved timestamp", async () => {
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
    mockedGetTranscript.mockResolvedValue([]);
    mockedGetEvidence.mockResolvedValue([
      {
        evidence_id: "evidence-1",
        rule_id: "problem_phrase",
        label: "Problem statement",
        transcript_turn_id: "turn-1",
        start_ms: 1500,
        end_ms: 2000,
        quote: "I need help with this error.",
      },
    ]);
    const { container } = render(<CallDetailPage callId="call-1" />);
    const currentTimeSetter = vi.spyOn(
      HTMLMediaElement.prototype,
      "currentTime",
      "set",
    );
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();

    fireEvent.click(
      await within(container).findByText("I need help with this error."),
    );

    expect(currentTimeSetter).toHaveBeenCalledWith(1.5);
    expect(within(container).getByText("Problem statement")).toBeTruthy();
  });

  it("searches, filters, and keeps the active turn visible", async () => {
    mockedGetCallDetail.mockResolvedValue({
      call_id: "call-1",
      agent_name: "Agent",
      customer_name: "Customer",
      created_at: "2026-08-22",
      processing_status: "completed",
      audio_channels: 1,
      failure_reason: null,
      transcript_turn_count: 3,
    });
    mockedGetTranscript.mockResolvedValue([
      {
        transcript_turn_id: "turn-1",
        speaker: "agent",
        start_ms: 0,
        end_ms: 1000,
        text: "Welcome to support",
      },
      {
        transcript_turn_id: "turn-2",
        speaker: "customer",
        start_ms: 1000,
        end_ms: 2000,
        text: "I need a password reset",
      },
      {
        transcript_turn_id: "turn-3",
        speaker: "agent",
        start_ms: 2000,
        end_ms: 3000,
        text: "I can help with that",
      },
    ]);
    const scrollIntoView = vi.fn();
    const originalScrollIntoView = Object.getOwnPropertyDescriptor(
      HTMLElement.prototype,
      "scrollIntoView",
    );
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
    const searchLog = vi.spyOn(console, "info").mockImplementation(() => {});
    const { container } = render(<CallDetailPage callId="call-1" />);
    const page = within(container);

    await page.findByText("Welcome to support");
    expect(page.getByRole("region", { name: "Agent messages" })).toBeTruthy();
    expect(
      page.getByRole("region", { name: "Customer messages" }),
    ).toBeTruthy();
    expect(page.getByText("0.00s–1.00s")).toBeTruthy();
    const audio = container.querySelector("audio") as HTMLAudioElement;
    let playerTime = 4;
    Object.defineProperty(audio, "currentTime", {
      configurable: true,
      get: () => playerTime,
      set: (value: number) => {
        playerTime = value;
      },
    });
    fireEvent.timeUpdate(audio);

    fireEvent.change(
      page.getByRole("searchbox", { name: "Search transcript" }),
      {
        target: { value: "password" },
      },
    );

    expect(page.getByText("I need a password reset")).toBeTruthy();
    expect(page.queryByText("Welcome to support")).toBeNull();
    expect(searchLog).toHaveBeenCalledWith("transcript_search_updated", {
      query_length: 8,
      speaker_filter: "all",
    });

    fireEvent.click(page.getByText("I need a password reset"));
    await waitFor(() => expect(scrollIntoView).toHaveBeenCalled());
    fireEvent.change(page.getByRole("combobox", { name: "Show speaker" }), {
      target: { value: "agent" },
    });

    expect(page.getByText("I need a password reset")).toBeTruthy();
    expect(
      page.getByText("Showing the active turn alongside your filters."),
    ).toBeTruthy();

    if (originalScrollIntoView)
      Object.defineProperty(
        HTMLElement.prototype,
        "scrollIntoView",
        originalScrollIntoView,
      );
    else
      delete (HTMLElement.prototype as { scrollIntoView?: unknown })
        .scrollIntoView;
  });

  it("places messages in speaker lanes with their complete saved ranges", async () => {
    mockedGetCallDetail.mockResolvedValue({
      call_id: "call-1",
      agent_name: "Agent",
      customer_name: "Customer",
      created_at: "2026-08-22",
      processing_status: "completed",
      audio_channels: 2,
      failure_reason: null,
      transcript_turn_count: 3,
    });
    mockedGetTranscript.mockResolvedValue([
      {
        transcript_turn_id: "agent-turn",
        speaker: "agent",
        start_ms: 22020,
        end_ms: 44900,
        text: "The requested item will be sent to your address.",
      },
      {
        transcript_turn_id: "customer-turn",
        speaker: "customer",
        start_ms: 30000,
        end_ms: 32000,
        text: "Please confirm the address.",
      },
      {
        transcript_turn_id: "unknown-turn",
        speaker: "unknown",
        start_ms: 33000,
        end_ms: 34000,
        text: "Unattributed speech.",
      },
    ]);

    render(<CallDetailPage callId="call-1" />);

    const agentLane = await screen.findByRole("region", {
      name: "Agent messages",
    });
    const customerLane = screen.getByRole("region", {
      name: "Customer messages",
    });
    const unknownLane = screen.getByRole("region", {
      name: "Unattributed messages",
    });

    expect(
      within(agentLane).getByText(
        "The requested item will be sent to your address.",
      ),
    ).toBeTruthy();
    expect(within(agentLane).getByText("22.02s–44.90s")).toBeTruthy();
    expect(
      within(customerLane).getByText("Please confirm the address."),
    ).toBeTruthy();
    expect(within(unknownLane).getByText("Unattributed speech.")).toBeTruthy();
  });

  it("offers the explicit unknown-speaker filter for mono transcripts", async () => {
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
        speaker: "unknown",
        start_ms: 0,
        end_ms: 1000,
        text: "Unattributed speech",
      },
    ]);

    const { container } = render(<CallDetailPage callId="call-1" />);

    const filter = await within(container).findByRole("combobox", {
      name: "Show speaker",
    });
    expect(
      within(filter).getByRole("option", { name: "Unknown speaker" }),
    ).toBeTruthy();
    fireEvent.change(filter, { target: { value: "unknown" } });
    expect(within(container).getByText("Unattributed speech")).toBeTruthy();
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

  it("opens a score explanation drawer and jumps to its exact evidence", async () => {
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
        speaker: "customer",
        start_ms: 1500,
        end_ms: 2000,
        text: "This issue is still not working.",
      },
    ]);
    mockedCalculatePriority.mockResolvedValue({
      call_id: "call-1",
      score: 60,
      scoring_version: "radar-priority-v1",
      factors: [
        {
          factor_key: "unresolved_phrase",
          label: "Unresolved customer concern",
          contribution: 60,
          evidence_id: "evidence-1",
          transcript_turn_id: "turn-1",
          start_ms: 1500,
          end_ms: 2000,
        },
      ],
    });
    const audioPlay = vi
      .spyOn(HTMLMediaElement.prototype, "play")
      .mockResolvedValue();
    const currentTimeSetter = vi.spyOn(
      HTMLMediaElement.prototype,
      "currentTime",
      "set",
    );

    render(<CallDetailPage callId="call-1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Show me why" }));

    expect(screen.getByRole("dialog")).toBeTruthy();
    fireEvent.click(
      screen.getByRole("button", { name: /Unresolved customer concern/ }),
    );

    expect(screen.getByText("Evidence details")).toBeTruthy();
    expect(
      within(screen.getByRole("dialog")).getByText(
        "This issue is still not working.",
      ),
    ).toBeTruthy();
    expect(currentTimeSetter).toHaveBeenCalledWith(1.5);
    expect(audioPlay).toHaveBeenCalled();
  });

  it("opens an analysis claim using its saved transcript evidence", async () => {
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
        transcript_turn_id: "turn-claim",
        speaker: "customer",
        start_ms: 2500,
        end_ms: 3000,
        text: "I need help with my account.",
      },
    ]);
    mockedGetAnalysis.mockResolvedValue({
      intent: "Support",
      mood: "negative",
      resolution: "unresolved",
      summary: "Summary",
      manager_brief: "Review the concern.",
      recommended_action: "Follow up.",
      claims: [
        {
          claim: "Customer support concern",
          transcript_turn_id: "turn-claim",
          quote: "I need help with my account.",
          start_ms: 2500,
          end_ms: 3000,
        },
      ],
      model_version: "test-v1",
    });
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
    const currentTimeSetter = vi.spyOn(
      HTMLMediaElement.prototype,
      "currentTime",
      "set",
    );

    render(<CallDetailPage callId="call-1" />);
    fireEvent.click(
      await screen.findByRole("button", {
        name: /Customer support concern/,
      }),
    );

    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByText("Analysis claim")).toBeTruthy();
    expect(currentTimeSetter).toHaveBeenCalledWith(2.5);
  });
});
