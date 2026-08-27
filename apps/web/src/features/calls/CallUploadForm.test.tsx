import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { clearAllCallData, processCall, registerCall } from "../../api/calls";
import { CallUploadForm } from "./CallUploadForm";

vi.mock("../../api/calls", () => ({
  clearAllCallData: vi.fn(),
  processCall: vi.fn(),
  registerCall: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

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

  it("uploads a batch of selected audio files and clears stored data", async () => {
    vi.mocked(registerCall)
      .mockResolvedValueOnce({
        call_id: "call-1",
        job_id: "job-1",
        status: "queued",
      })
      .mockResolvedValueOnce({
        call_id: "call-2",
        job_id: "job-2",
        status: "queued",
      });
    vi.mocked(processCall).mockResolvedValue({
      job_id: "job-1",
      status: "queued",
      audio_channels: null,
      failure_reason: null,
      transcript_turn_count: 0,
    });
    vi.mocked(clearAllCallData).mockResolvedValue({
      calls_deleted: 2,
      processing_jobs_deleted: 2,
      transcript_turns_deleted: 0,
      analysis_rows_deleted: 0,
      upload_files_deleted: 4,
    });

    render(<CallUploadForm />);

    fireEvent.change(screen.getByLabelText("Audio files"), {
      target: {
        files: [
          new File(["audio 1"], "call-1.wav", { type: "audio/wav" }),
          new File(["audio 2"], "call-2.wav", { type: "audio/wav" }),
        ],
      },
    });

    fireEvent.change(screen.getByLabelText("Agent name"), {
      target: { value: "Agent" },
    });
    fireEvent.change(screen.getByLabelText("Customer name"), {
      target: { value: "Customer" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Upload batch" }));

    await waitFor(() => expect(registerCall).toHaveBeenCalledTimes(2));
    expect(processCall).toHaveBeenCalledTimes(2);
    expect(screen.getByText("Registered and queued 2 calls.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Clear all data" }));

    await waitFor(() => expect(clearAllCallData).toHaveBeenCalledTimes(1));
    expect(
      screen.getByText("Cleared 2 stored calls and removed 4 uploaded files."),
    ).toBeTruthy();
  });
});
