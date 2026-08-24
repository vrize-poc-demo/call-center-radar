import {
  act,
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
import { selectActiveTranscriptTurn } from "./transcriptPlayback";

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
    mood_shifts: [],
    false_resolution: null,
    repeated_questions: [],
    silence_windows: [],
    conversation_balance: {
      agent_talk_ms: 0,
      customer_talk_ms: 0,
      agent_share_pct: 0,
      customer_share_pct: 0,
    },
    model_version: "test-v1",
  });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.resetAllMocks();
});

describe("CallDetailPage", () => {
  it("shows the persisted concise summary before the manager brief", async () => {
    mockedGetCallDetail.mockResolvedValue({
      call_id: "call-1",
      agent_name: "Agent",
      customer_name: "Customer",
      created_at: "2026-08-23 09:00:00",
      processing_status: "completed",
      audio_channels: 2,
      transcript_turn_count: 1,
      failure_reason: null,
    });
    mockedGetTranscript.mockResolvedValue([]);

    render(<CallDetailPage callId="call-1" />);

    expect(
      await screen.findByRole("heading", { name: "Summary" }),
    ).toBeTruthy();
    expect(screen.getByText("Summary", { selector: "p" })).toBeTruthy();
    expect(screen.getByText("Review the support concern.")).toBeTruthy();
  });

  it("prefers the latest active turn when stereo transcript segments overlap", () => {
    const turns = [
      {
        transcript_turn_id: "agent-long-turn",
        speaker: "agent" as const,
        start_ms: 11380,
        end_ms: 21020,
        text: "Long agent segment",
      },
      {
        transcript_turn_id: "customer-current-turn",
        speaker: "customer" as const,
        start_ms: 16300,
        end_ms: 18100,
        text: "Current customer speech",
      },
    ];

    expect(selectActiveTranscriptTurn(turns, 17000)?.transcript_turn_id).toBe(
      "customer-current-turn",
    );
  });

  it("uses the shortest active turn as a deterministic equal-start tie-breaker", () => {
    const turns = [
      {
        transcript_turn_id: "long-turn",
        speaker: "agent" as const,
        start_ms: 1000,
        end_ms: 5000,
        text: "Long turn",
      },
      {
        transcript_turn_id: "short-turn",
        speaker: "customer" as const,
        start_ms: 1000,
        end_ms: 2000,
        text: "Short turn",
      },
    ];

    expect(selectActiveTranscriptTurn(turns, 1500)?.transcript_turn_id).toBe(
      "short-turn",
    );
  });

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
    expect(
      screen.getByRole("heading", { name: "Conversation Timeline" }),
    ).toBeTruthy();
    const panelHeadings = screen
      .getAllByRole("heading", { level: 2 })
      .map((heading) => heading.textContent);
    expect(panelHeadings.indexOf("Conversation Timeline")).toBeLessThan(
      panelHeadings.indexOf("Call analysis"),
    );
    expect(panelHeadings.indexOf("Call analysis")).toBeLessThan(
      panelHeadings.indexOf("Radar Priority"),
    );
    expect(panelHeadings.indexOf("Radar Priority")).toBeLessThan(
      panelHeadings.indexOf("Processing"),
    );
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

  it("refreshes a processing call until its completed transcript is available", async () => {
    vi.useFakeTimers();
    mockedGetCallDetail
      .mockResolvedValueOnce({
        call_id: "call-1",
        agent_name: "Agent",
        customer_name: "Customer",
        created_at: "2026-08-22",
        processing_status: "transcribing",
        audio_channels: null,
        failure_reason: null,
        transcript_turn_count: 0,
      })
      .mockResolvedValueOnce({
        call_id: "call-1",
        agent_name: "Agent",
        customer_name: "Customer",
        created_at: "2026-08-22",
        processing_status: "completed",
        audio_channels: 1,
        failure_reason: null,
        transcript_turn_count: 1,
      });
    mockedGetTranscript.mockResolvedValueOnce([]).mockResolvedValueOnce([
      {
        transcript_turn_id: "turn-1",
        speaker: "agent",
        start_ms: 0,
        end_ms: 1000,
        text: "Completed transcript turn",
      },
    ]);

    render(<CallDetailPage callId="call-1" />);
    await act(async () => {});
    expect(screen.getAllByText("transcribing")).toHaveLength(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_000);
    });

    expect(screen.getByText("Completed transcript turn")).toBeTruthy();
    expect(mockedGetCallDetail).toHaveBeenCalledTimes(2);
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
    expect(
      page.getByRole("list", {
        name: "Agent and customer conversation timeline",
      }),
    ).toBeTruthy();
    expect(page.getAllByRole("listitem")).toHaveLength(3);
    expect(page.getByText("0.00")).toBeTruthy();
    expect(page.getByText("10.00")).toBeTruthy();
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
      page.getByRole("searchbox", { name: "Search conversation" }),
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

  it("renders chronological speaker turns in agent and customer lanes", async () => {
    mockedGetCallDetail.mockResolvedValue({
      call_id: "call-1",
      agent_name: "Agent",
      customer_name: "Customer",
      created_at: "2026-08-22",
      processing_status: "completed",
      audio_channels: 2,
      failure_reason: null,
      transcript_turn_count: 4,
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
        transcript_turn_id: "customer-address",
        speaker: "customer",
        start_ms: 35000,
        end_ms: 37000,
        text: "Fourth Ranch, Oregon, 72504.",
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
    const currentTimeSetter = vi.spyOn(
      HTMLMediaElement.prototype,
      "currentTime",
      "set",
    );
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();

    const timeline = await screen.findByRole("list", {
      name: "Agent and customer conversation timeline",
    });
    const rows = within(timeline).getAllByRole("listitem");
    const agentButton = screen.getByRole("button", {
      name: "Agent 22.02s–44.90s: The requested item will be sent to your address.",
    });
    const customerButton = screen.getByRole("button", {
      name: "Customer 30.00s–32.00s: Please confirm the address.",
    });
    const agentRow = agentButton.closest("[role='listitem']");
    const customerRow = customerButton.closest("[role='listitem']");

    expect(rows).toHaveLength(4);
    expect(agentRow).toBeTruthy();
    expect(customerRow).toBeTruthy();

    expect(agentRow?.classList.contains("agent-turn")).toBe(true);
    expect(customerRow?.classList.contains("customer-turn")).toBe(true);
    expect(screen.getByText("0.00")).toBeTruthy();
    expect(screen.getByText("50.00")).toBeTruthy();
    expect(screen.queryByText("Overlap")).toBeNull();
    expect(screen.getByText("Fourth Ranch, Oregon, 72504.")).toBeTruthy();
    expect(screen.getByText("Unattributed speech.")).toBeTruthy();

    fireEvent.click(agentButton);
    expect(currentTimeSetter).toHaveBeenCalledWith(22.02);
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
      expect(
        screen.getByText("Synced turn").closest(".active-turn"),
      ).toBeTruthy(),
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
      mood_shifts: [
        {
          from_mood: "neutral",
          to_mood: "negative",
          reason: "The customer reports a support concern.",
          transcript_turn_id: "turn-claim",
          quote: "I need help with my account.",
          start_ms: 2500,
          end_ms: 3000,
        },
      ],
      false_resolution: null,
      repeated_questions: [],
      silence_windows: [],
      conversation_balance: {
        agent_talk_ms: 0,
        customer_talk_ms: 0,
        agent_share_pct: 0,
        customer_share_pct: 0,
      },
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

  it("opens a mood shift at its saved transcript and audio timestamp", async () => {
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
        transcript_turn_id: "turn-shift",
        speaker: "customer",
        start_ms: 4000,
        end_ms: 5000,
        text: "Thank you, it is working now.",
      },
    ]);
    mockedGetAnalysis.mockResolvedValue({
      intent: "Support",
      mood: "positive",
      resolution: "resolved",
      summary: "The problem was resolved.",
      manager_brief: "No follow-up is needed.",
      recommended_action: "Monitor.",
      claims: [],
      mood_shifts: [
        {
          from_mood: "negative",
          to_mood: "positive",
          reason: "The customer confirms the service is working.",
          transcript_turn_id: "turn-shift",
          quote: "Thank you, it is working now.",
          start_ms: 4000,
          end_ms: 5000,
        },
      ],
      false_resolution: null,
      repeated_questions: [],
      silence_windows: [],
      conversation_balance: {
        agent_talk_ms: 0,
        customer_talk_ms: 0,
        agent_share_pct: 0,
        customer_share_pct: 0,
      },
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
      await screen.findByRole("button", { name: /negative to positive/ }),
    );

    expect(screen.getByText("Mood shift: negative to positive")).toBeTruthy();
    expect(currentTimeSetter).toHaveBeenCalledWith(4);
  });

  it("shows a false resolution with saved evidence jumps", async () => {
    mockedGetCallDetail.mockResolvedValue({
      call_id: "call-1",
      agent_name: "Agent",
      customer_name: "Customer",
      created_at: "2026-08-23",
      processing_status: "completed",
      audio_channels: 1,
      failure_reason: null,
      transcript_turn_count: 2,
    });
    mockedGetTranscript.mockResolvedValue([
      {
        transcript_turn_id: "resolution-turn",
        speaker: "agent",
        start_ms: 1000,
        end_ms: 1500,
        text: "Your card is fixed now.",
      },
      {
        transcript_turn_id: "contradiction-turn",
        speaker: "customer",
        start_ms: 3000,
        end_ms: 3500,
        text: "It still is not working.",
      },
    ]);
    mockedGetAnalysis.mockResolvedValue({
      intent: "Card support",
      mood: "negative",
      resolution: "resolved",
      summary: "The customer disputes a stated card resolution.",
      manager_brief: "Review the unresolved card issue.",
      recommended_action: "Contact the customer.",
      claims: [],
      mood_shifts: [],
      false_resolution: {
        rule_id: "false_resolution_contradiction_v1",
        resolution: {
          claim: "Agent stated the issue was resolved",
          transcript_turn_id: "resolution-turn",
          quote: "Your card is fixed now.",
          start_ms: 1000,
          end_ms: 1500,
        },
        contradiction: {
          claim: "Customer later contradicted the resolution",
          transcript_turn_id: "contradiction-turn",
          quote: "It still is not working.",
          start_ms: 3000,
          end_ms: 3500,
        },
      },
      repeated_questions: [],
      silence_windows: [],
      conversation_balance: {
        agent_talk_ms: 0,
        customer_talk_ms: 0,
        agent_share_pct: 0,
        customer_share_pct: 0,
      },
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
      await screen.findByRole("button", { name: "Show later contradiction" }),
    );

    expect(screen.getByText("Analysis claim")).toBeTruthy();
    expect(currentTimeSetter).toHaveBeenCalledWith(3);
  });

  it("opens the repeated request at its saved transcript and audio timestamp", async () => {
    mockedGetCallDetail.mockResolvedValue({
      call_id: "call-1",
      agent_name: "Agent",
      customer_name: "Customer",
      created_at: "2026-08-23",
      processing_status: "completed",
      audio_channels: 1,
      failure_reason: null,
      transcript_turn_count: 2,
    });
    mockedGetTranscript.mockResolvedValue([
      {
        transcript_turn_id: "question-one",
        speaker: "customer",
        start_ms: 1000,
        end_ms: 1500,
        text: "What time is my appointment?",
      },
      {
        transcript_turn_id: "question-two",
        speaker: "customer",
        start_ms: 4000,
        end_ms: 4500,
        text: "What time is my appointment?",
      },
    ]);
    mockedGetAnalysis.mockResolvedValue({
      intent: "Appointment question",
      mood: "neutral",
      resolution: "unclear",
      summary: "The customer repeated an appointment-time question.",
      manager_brief: "Check why the appointment time was not answered.",
      recommended_action: "Confirm the appointment time.",
      claims: [],
      mood_shifts: [],
      false_resolution: null,
      repeated_questions: [
        {
          rule_id: "repeated_question_exact_v1",
          speaker: "customer",
          original: {
            claim: "Original information request",
            transcript_turn_id: "question-one",
            quote: "What time is my appointment?",
            start_ms: 1000,
            end_ms: 1500,
          },
          repeated: {
            claim: "Repeated information request",
            transcript_turn_id: "question-two",
            quote: "What time is my appointment?",
            start_ms: 4000,
            end_ms: 4500,
          },
        },
      ],
      silence_windows: [],
      conversation_balance: {
        agent_talk_ms: 0,
        customer_talk_ms: 1000,
        agent_share_pct: 0,
        customer_share_pct: 100,
      },
      model_version: "test-v1",
    });
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
    const currentTimeSetter = vi.spyOn(
      HTMLMediaElement.prototype,
      "currentTime",
      "set",
    );

    render(<CallDetailPage callId="call-1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Show repeat" }));

    expect(screen.getByText("Analysis claim")).toBeTruthy();
    expect(currentTimeSetter).toHaveBeenCalledWith(4);
  });

  it("shows customer treatment signals with saved evidence jumps", async () => {
    mockedGetCallDetail.mockResolvedValue({
      call_id: "call-1",
      agent_name: "Agent",
      customer_name: "Customer",
      created_at: "2026-08-23",
      processing_status: "completed",
      audio_channels: 1,
      failure_reason: null,
      transcript_turn_count: 1,
    });
    mockedGetTranscript.mockResolvedValue([
      {
        transcript_turn_id: "treatment-turn",
        speaker: "customer",
        start_ms: 2300,
        end_ms: 3200,
        text: "This is unacceptable, let me speak to your supervisor.",
      },
    ]);
    mockedGetAnalysis.mockResolvedValue({
      intent: "Escalation request",
      mood: "negative",
      resolution: "unresolved",
      summary: "The customer escalated a concern.",
      manager_brief: "Review the interaction supportively.",
      recommended_action: "Check whether the agent needs support.",
      claims: [],
      mood_shifts: [],
      false_resolution: null,
      repeated_questions: [],
      treatment_signals: [
        {
          rule_id: "customer_escalation_or_frustration_v1",
          label: "Explicit customer escalation or frustration",
          evidence: {
            claim: "Explicit customer escalation or frustration",
            transcript_turn_id: "treatment-turn",
            quote: "This is unacceptable, let me speak to your supervisor.",
            start_ms: 2300,
            end_ms: 3200,
          },
        },
      ],
      silence_windows: [],
      conversation_balance: {
        agent_talk_ms: 0,
        customer_talk_ms: 900,
        agent_share_pct: 0,
        customer_share_pct: 100,
      },
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
      await screen.findByRole("button", { name: "Show transcript evidence" }),
    );

    expect(screen.getByText("Analysis claim")).toBeTruthy();
    expect(currentTimeSetter).toHaveBeenCalledWith(2.3);
  });

  it("shows balance and opens a silence window at the next speech turn", async () => {
    mockedGetCallDetail.mockResolvedValue({
      call_id: "call-1",
      agent_name: "Agent",
      customer_name: "Customer",
      created_at: "2026-08-23",
      processing_status: "completed",
      audio_channels: 1,
      failure_reason: null,
      transcript_turn_count: 2,
    });
    mockedGetTranscript.mockResolvedValue([
      {
        transcript_turn_id: "before-silence",
        speaker: "agent",
        start_ms: 0,
        end_ms: 1000,
        text: "Let me check.",
      },
      {
        transcript_turn_id: "after-silence",
        speaker: "customer",
        start_ms: 5000,
        end_ms: 7000,
        text: "I still need help.",
      },
    ]);
    mockedGetAnalysis.mockResolvedValue({
      intent: "Support",
      mood: "neutral",
      resolution: "unclear",
      summary: "The customer needs account support.",
      manager_brief: "Review the support interaction.",
      recommended_action: "Follow up.",
      claims: [],
      mood_shifts: [],
      false_resolution: null,
      repeated_questions: [],
      silence_windows: [
        {
          before: {
            claim: "Speech before silence",
            transcript_turn_id: "before-silence",
            quote: "Let me check.",
            start_ms: 0,
            end_ms: 1000,
          },
          after: {
            claim: "Speech after silence",
            transcript_turn_id: "after-silence",
            quote: "I still need help.",
            start_ms: 5000,
            end_ms: 7000,
          },
          duration_ms: 4000,
        },
      ],
      conversation_balance: {
        agent_talk_ms: 1000,
        customer_talk_ms: 2000,
        agent_share_pct: 33.3,
        customer_share_pct: 66.7,
      },
      model_version: "test-v1",
    });
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
    const currentTimeSetter = vi.spyOn(
      HTMLMediaElement.prototype,
      "currentTime",
      "set",
    );

    render(<CallDetailPage callId="call-1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Show after" }));

    expect(screen.getByText(/Agent 33.3%/)).toBeTruthy();
    expect(screen.getByText("Analysis claim")).toBeTruthy();
    expect(currentTimeSetter).toHaveBeenCalledWith(5);
  });
});
