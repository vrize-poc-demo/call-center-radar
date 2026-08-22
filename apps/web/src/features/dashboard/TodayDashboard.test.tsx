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
