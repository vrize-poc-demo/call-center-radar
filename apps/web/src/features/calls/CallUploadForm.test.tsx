import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { processCall, registerCall } from "../../api/calls";
import { CallUploadForm } from "./CallUploadForm";

vi.mock("../../api/calls", () => ({
  processCall: vi.fn(),
  registerCall: vi.fn(),
}));

afterEach(() => vi.resetAllMocks());

describe("CallUploadForm", () => {
  it("starts processing after registration without waiting for transcription", async () => {
    vi.mocked(registerCall).mockResolvedValue({
      call_id: "call-1",
      job_id: "job-1",
      status: "queued",
    });
    vi.mocked(processCall).mockResolvedValue({
      job_id: "job-1",
      status: "queued",
      audio_channels: null,
      failure_reason: null,
      transcript_turn_count: 0,
    });
    const { container } = render(<CallUploadForm />);

    fireEvent.change(screen.getByLabelText("Call recording"), {
      target: {
        files: [new File(["audio"], "call.wav", { type: "audio/wav" })],
      },
    });
    fireEvent.change(screen.getByLabelText("Agent name"), {
      target: { value: "Agent" },
    });
    fireEvent.change(screen.getByLabelText("Customer name"), {
      target: { value: "Customer" },
    });
    fireEvent.submit(container.querySelector("form") as HTMLFormElement);

    await waitFor(() => expect(processCall).toHaveBeenCalledWith("job-1"));
    expect(
      screen.getByText(
        "Processing has started. You can register another call or keep navigating while it runs.",
      ),
    ).toBeTruthy();
    expect(
      screen
        .getByRole("link", { name: "Open call detail" })
        .getAttribute("href"),
    ).toBe("?call=call-1");
  });
});
