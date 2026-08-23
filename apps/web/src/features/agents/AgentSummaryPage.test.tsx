import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getAgentSummaries } from "../../api/calls";
import { AgentSummaryPage } from "./AgentSummaryPage";

vi.mock("../../api/calls", () => ({ getAgentSummaries: vi.fn() }));

const mockedGetAgentSummaries = vi.mocked(getAgentSummaries);

beforeEach(() => {
  vi.spyOn(console, "info").mockImplementation(() => undefined);
  vi.spyOn(console, "warn").mockImplementation(() => undefined);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.resetAllMocks();
});

describe("AgentSummaryPage", () => {
  it("renders supportive agent summaries and recent call drill-downs", async () => {
    mockedGetAgentSummaries.mockResolvedValue([
      {
        agent_name: "Vipin",
        calls_handled: 3,
        difficult_calls: 2,
        estimated_satisfaction: 58,
        average_handle_time_ms: 125_000,
        calls_with_handle_time: 3,
        resolved_count: 1,
        resolved_rate: 33,
        average_priority: 62,
        treatment_signal_count: 1,
        unresolved_count: 1,
        false_resolution_count: 0,
        high_risk_count: 1,
        coaching_note:
          "Review difficult interactions supportively and check whether the agent needs backup.",
        recent_call_ids: ["call-1", "call-2"],
      },
      {
        agent_name: "Susmitha",
        calls_handled: 1,
        difficult_calls: 0,
        estimated_satisfaction: 92,
        average_handle_time_ms: null,
        calls_with_handle_time: 0,
        resolved_count: 1,
        resolved_rate: 100,
        average_priority: 10,
        treatment_signal_count: 0,
        unresolved_count: 0,
        false_resolution_count: 0,
        high_risk_count: 0,
        coaching_note: "No coaching concern stands out from analyzed evidence.",
        recent_call_ids: ["call-3"],
      },
    ]);

    render(<AgentSummaryPage />);

    expect(
      await screen.findByRole("heading", { name: "Agent support" }),
    ).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Vipin" })).toBeTruthy();
    expect(screen.getByText("Support check")).toBeTruthy();
    expect(
      screen.getByText(
        "Review difficult interactions supportively and check whether the agent needs backup.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("Estimated satisfaction")).toBeTruthy();
    expect(
      screen.getAllByText("Open recent call")[0].getAttribute("href"),
    ).toBe("/?call=call-1");
    expect(screen.getAllByText("Avg handle time")[0]).toBeTruthy();
    expect(screen.getAllByText("2:05")).toHaveLength(2);
    expect(screen.getByText("1 (33%)")).toBeTruthy();
    expect(screen.getByText("62")).toBeTruthy();
    expect(screen.getByText("—")).toBeTruthy();
  });

  it("shows an empty state until analyzed calls exist", async () => {
    mockedGetAgentSummaries.mockResolvedValue([]);

    render(<AgentSummaryPage />);

    expect(
      await screen.findByRole("heading", { name: "No agent patterns yet" }),
    ).toBeTruthy();
  });

  it("shows a useful failure state", async () => {
    mockedGetAgentSummaries.mockRejectedValue(
      new Error("Agent summary unavailable."),
    );

    render(<AgentSummaryPage />);

    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toBe(
        "Agent summary unavailable.",
      ),
    );
  });
});
