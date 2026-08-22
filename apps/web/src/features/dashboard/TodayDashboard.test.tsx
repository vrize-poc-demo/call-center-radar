import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getDashboardTriage } from "../../api/calls";
import { TodayDashboard } from "./TodayDashboard";

vi.mock("../../api/calls", () => ({ getDashboardTriage: vi.fn() }));

const mockedGetDashboardTriage = vi.mocked(getDashboardTriage);

beforeEach(() => {
  vi.spyOn(console, "info").mockImplementation(() => undefined);
  vi.spyOn(console, "warn").mockImplementation(() => undefined);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.resetAllMocks();
});

describe("TodayDashboard", () => {
  it("summarizes risk and shows only the three most urgent calls", async () => {
    mockedGetDashboardTriage.mockResolvedValue(
      Array.from({ length: 4 }, (_, index) => ({
        call_id: `call-${index}`,
        created_at: "2026-08-22 09:00:00",
        radar_priority: 100,
        risk_level: "high" as const,
        analysis: {
          intent: "Support",
          mood: "negative" as const,
          resolution: "unresolved" as const,
          manager_brief: `Escalate call ${index}`,
          recommended_action: "Contact the customer.",
          model_version: "test-v1",
          analysis_version: 1,
          analyzed_at: "2026-08-22 09:00:00",
        },
      })),
    );

    render(<TodayDashboard />);

    expect(await screen.findByRole("heading", { name: "Today" })).toBeTruthy();
    expect(screen.getAllByText("Needs attention").length).toBeGreaterThan(0);
    expect(screen.getAllByText("4").length).toBeGreaterThan(0);
    expect(screen.getAllByText("High risk").length).toBeGreaterThan(0);
    expect(screen.getByText("Escalate call 0")).toBeTruthy();
    expect(screen.queryByText("Escalate call 3")).toBeNull();
    expect(
      screen
        .getByRole("link", { name: /Escalate call 0/ })
        .getAttribute("href"),
    ).toBe("/?call=call-0");
  });

  it("explains the empty needs-attention state", async () => {
    mockedGetDashboardTriage.mockResolvedValue([]);

    render(<TodayDashboard />);

    expect(
      await screen.findByRole("heading", { name: "No urgent calls right now" }),
    ).toBeTruthy();
    expect(screen.getByText("Analyzed calls")).toBeTruthy();
  });

  it("ranks every call by priority and keeps drill-down navigation", async () => {
    mockedGetDashboardTriage.mockResolvedValue([
      { call_id: "low", created_at: "now", radar_priority: 10, risk_level: "low", analysis: { intent: "Low", mood: "neutral", resolution: "resolved", manager_brief: "Low", recommended_action: "Monitor", model_version: "v1", analysis_version: 1, analyzed_at: "now" } },
      { call_id: "high", created_at: "now", radar_priority: 90, risk_level: "high", analysis: { intent: "High", mood: "negative", resolution: "unresolved", manager_brief: "High", recommended_action: "Act", model_version: "v1", analysis_version: 1, analyzed_at: "now" } },
    ]);
    render(<TodayDashboard />);
    const links = await screen.findAllByRole("link", { name: /High|Low/ });
    expect(links.map((link) => link.getAttribute("href"))).toContain("/?call=high");
    expect(screen.getByRole("heading", { name: "All analyzed calls" })).toBeTruthy();
    expect(screen.getAllByText("High")[0]).toBeTruthy();
  });

  it("shows a useful failure state", async () => {
    mockedGetDashboardTriage.mockRejectedValue(
      new Error("Dashboard unavailable."),
    );

    render(<TodayDashboard />);

    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toBe(
        "Dashboard unavailable.",
      ),
    );
  });
});
