import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getServiceHealth } from "../../api/calls";
import { ServiceHealthStatusBar } from "./ServiceHealthStatusBar";

vi.mock("../../api/calls", () => ({
  getServiceHealth: vi.fn(),
}));

const mockedGetServiceHealth = vi.mocked(getServiceHealth);

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.resetAllMocks();
});

describe("ServiceHealthStatusBar", () => {
  it("shows the compact healthy state when every service is running", async () => {
    mockedGetServiceHealth.mockResolvedValue({
      status: "healthy",
      services: [
        {
          key: "database",
          label: "SQLite data store",
          status: "healthy",
          detail: "SQLite is reachable and ready to persist calls.",
          action_label: null,
          action_hint: null,
        },
      ],
    });

    render(<ServiceHealthStatusBar />);

    expect(await screen.findByText("Healthy")).toBeTruthy();
    expect(screen.getByText("All services running")).toBeTruthy();
  });

  it("opens per-service setup guidance for a missing local model", async () => {
    mockedGetServiceHealth.mockResolvedValue({
      status: "degraded",
      services: [
        {
          key: "ollama_server",
          label: "Local LLM server",
          status: "healthy",
          detail: "Ollama is reachable.",
          action_label: null,
          action_hint: null,
        },
        {
          key: "ollama_model",
          label: "Analysis model",
          status: "degraded",
          detail: "Ollama is running, but model qwen2.5:7b is not installed.",
          action_label: "Pull model",
          action_hint:
            "Run ollama pull qwen2.5:7b, or docker compose run --rm ollama-model.",
        },
      ],
    });

    render(<ServiceHealthStatusBar />);

    const details = await screen.findByRole("button", { name: /Needs setup/ });
    fireEvent.click(details);

    expect(screen.getByText("Service Health")).toBeTruthy();
    expect(screen.getByText("Analysis model")).toBeTruthy();
    expect(screen.getByText("Pull model")).toBeTruthy();
    expect(screen.getByText(/ollama pull qwen2.5:7b/)).toBeTruthy();
  });

  it("shows API recovery guidance when health polling fails", async () => {
    mockedGetServiceHealth.mockRejectedValue(new Error("offline"));
    const healthWarning = vi
      .spyOn(console, "warn")
      .mockImplementation(() => {});

    render(<ServiceHealthStatusBar />);

    const status = await screen.findByText("Not healthy");
    expect(status).toBeTruthy();
    expect(
      screen.getByText("API is not reachable. Start the backend and refresh."),
    ).toBeTruthy();
    expect(healthWarning).toHaveBeenCalledWith("service_health_poll_failed");
  });
});
