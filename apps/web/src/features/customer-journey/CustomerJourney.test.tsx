import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { getCustomerHistory } from "../../api/calls";
import { CustomerJourney } from "./CustomerJourney";

vi.mock("../../api/calls", () => ({ getCustomerHistory: vi.fn() }));

it("renders repeat issues and prior-call navigation", async () => {
  window.history.replaceState({}, "", "/?view=journey&journeyCall=current");
  vi.mocked(getCustomerHistory).mockResolvedValue([
    {
      call_id: "prior",
      created_at: "2026-08-01",
      processing_status: "completed",
      analysis_status: "analyzed",
      mood: "negative",
      resolution: "unresolved",
      issue: {
        key: "technical_support",
        label: "Technical support",
        repeated: true,
      },
    },
  ]);
  render(<CustomerJourney />);
  expect(await screen.findByText("Repeated: Technical support")).toBeTruthy();
  expect(
    screen.getByRole("link", { name: "Open call" }).getAttribute("href"),
  ).toBe("/?call=prior");
});
