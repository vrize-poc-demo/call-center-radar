import { ChangeEvent, FormEvent, useState } from "react";

import {
  CallRegistration,
  processCall,
  ProcessingStatus,
  registerCall,
} from "../../api/calls";

export function CallUploadForm() {
  const [result, setResult] = useState<CallRegistration | null>(null);
  const [processingResult, setProcessingResult] =
    useState<ProcessingStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [agentName, setAgentName] = useState("");
  const [customerName, setCustomerName] = useState("");

  async function populateNamesFromMetadata(
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const metadataFile = event.currentTarget.files?.[0];
    if (!metadataFile) return;

    try {
      const document = JSON.parse(await metadataFile.text()) as {
        agent?: { metadata?: { agent_name?: string } };
        caller?: { metadata?: { [key: string]: string | undefined } };
      };
      const agent = document.agent?.metadata?.agent_name;
      const customer = document.caller?.metadata?.["first and last name"];
      if (!agent || !customer)
        throw new Error("Metadata does not contain an agent and caller name.");
      setAgentName(agent);
      setCustomerName(customer);
      setError(null);
    } catch (metadataError) {
      setError(
        metadataError instanceof Error
          ? metadataError.message
          : "Metadata could not be read.",
      );
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    setError(null);
    setResult(null);
    setProcessingResult(null);
    setIsSubmitting(true);

    try {
      const registration = await registerCall(new FormData(form));
      setResult(registration);
      form.reset();
      setAgentName("");
      setCustomerName("");
    } catch (submissionError) {
      setError(
        submissionError instanceof Error
          ? submissionError.message
          : "The call could not be registered.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleProcessing() {
    if (!result) return;
    setError(null);
    setIsSubmitting(true);
    try {
      setProcessingResult(await processCall(result.job_id));
    } catch (processingError) {
      setError(
        processingError instanceof Error
          ? processingError.message
          : "The call could not be processed.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="upload-card" aria-labelledby="upload-title">
      <div>
        <p className="eyebrow">New call</p>
        <h2 id="upload-title">Register a call for review</h2>
        <p className="supporting-copy">
          Upload an MP3 or WAV recording, then enter names or load them from
          Call Radar JSON metadata.
        </p>
      </div>

      <form className="upload-form" onSubmit={handleSubmit}>
        <label>
          Call recording
          <input
            accept="audio/mpeg,audio/wav,.mp3,.wav"
            name="audio"
            required
            type="file"
          />
        </label>
        <label>
          Call metadata
          <input
            accept="application/json,.json"
            name="metadata"
            onChange={populateNamesFromMetadata}
            type="file"
          />
          <span className="field-hint">
            Optional: selecting JSON fills the editable fields below.
          </span>
        </label>
        <label>
          Agent name
          <input
            maxLength={120}
            name="agent_name"
            onChange={(event) => setAgentName(event.target.value)}
            required
            type="text"
            value={agentName}
          />
        </label>
        <label>
          Customer name
          <input
            maxLength={120}
            name="customer_name"
            onChange={(event) => setCustomerName(event.target.value)}
            required
            type="text"
            value={customerName}
          />
        </label>
        <button disabled={isSubmitting} type="submit">
          {isSubmitting ? "Registering…" : "Register call"}
        </button>
      </form>

      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}
      {result ? (
        <div className="processing-status" role="status">
          <p className="form-success">
            Call registered. Processing status:{" "}
            <strong>{processingResult?.status ?? result.status}</strong>.
          </p>
          {processingResult ? (
            <p className="field-hint">
              {processingResult.status === "completed"
                ? `Validated ${processingResult.audio_channels === 1 ? "mono" : "stereo"} audio.`
                : `Processing failed: ${processingResult.failure_reason}.`}
            </p>
          ) : (
            <div className="processing-actions">
              <button
                disabled={isSubmitting}
                onClick={handleProcessing}
                type="button"
              >
                Run processing skeleton
              </button>
              <a href={`?call=${result.call_id}`}>Open call detail</a>
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
