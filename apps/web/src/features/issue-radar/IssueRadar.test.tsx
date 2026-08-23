import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getDashboardTriage, getIssueRadar } from "../../api/calls";
import { IssueRadar } from "./IssueRadar";

vi.mock("../../api/calls", () => ({
  getDashboardTriage: vi.fn(),
  getIssueRadar: vi.fn(),
}));

const mockedGetDashboardTriage = vi.mocked(getDashboardTriage);
const mockedGetIssueRadar = vi.mocked(getIssueRadar);

beforeEach(() => {
  vi.spyOn(console, "info").mockImplementation(() => undefined);
  vi.spyOn(console, "warn").mockImplementation(() => undefined);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.resetAllMocks();
});

describe("IssueRadar", () => {
  it("shows clear critical, emerging, and stable issue labels", async () => {
    mockedGetIssueRadar.mockResolvedValue([
      group(
        "technical_support",
        "Technical support",
        "emerging",
        "critical-call",
        ["critical-call", "related-call"],
      ),
      group(
        "billing_and_payments",
        "Billing and payments",
        "stable",
        "stable-call",
        ["stable-call"],
      ),
    ]);
    mockedGetDashboardTriage.mockResolvedValue([
      triageCall("critical-call", "high", "unresolved"),
      triageCall("stable-call", "low", "resolved"),
    ]);

    render(<IssueRadar />);

    expect(
      await screen.findByRole("heading", { name: "Issue Radar" }),
    ).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "Technical support" }),
    ).toBeTruthy();
    expect(screen.getByText("Critical")).toBeTruthy();
    expect(screen.getByText("Emerging")).toBeTruthy();
    expect(screen.getByText("Stable")).toBeTruthy();
  });

  it("opens a representative call and exposes related-call drill-down", async () => {
    mockedGetIssueRadar.mockResolvedValue([
      group(
        "technical_support",
        "Technical support",
        "emerging",
        "representative",
        ["representative", "related"],
      ),
    ]);
    mockedGetDashboardTriage.mockResolvedValue([]);

    render(<IssueRadar />);

    const representative = await screen.findByRole("link", {
      name: "Inspect representative call",
    });
    expect(representative.getAttribute("href")).toBe("/?call=representative");
    expect(screen.getByText("Open related calls (1)")).toBeTruthy();
    expect(
      screen
        .getByRole("link", { name: "Open related call" })
        .getAttribute("href"),
    ).toBe("/?call=related");
  });
});

function group(
  key: string,
  label: string,
  trend: "emerging" | "stable",
  representativeCallId: string,
  relatedCallIds: string[],
) {
  return {
    key,
    label,
    call_count: relatedCallIds.length,
    current_window_count: 2,
    previous_window_count: 1,
    trend,
    representative_call_id: representativeCallId,
    related_call_ids: relatedCallIds,
  };
}

function triageCall(
  callId: string,
  riskLevel: "high" | "low",
  resolution: "unresolved" | "resolved",
) {
  return {
    call_id: callId,
    created_at: "now",
    radar_priority: riskLevel === "high" ? 90 : 10,
    risk_level: riskLevel,
    analysis: {
      intent: "Support",
      mood: "negative" as const,
      resolution,
      summary: "Summary",
      manager_brief: "Brief",
      recommended_action: "Action",
      model_version: "test-v1",
      analysis_version: 1,
      analyzed_at: "now",
      false_resolution: false,
    },
  };
}
