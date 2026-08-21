import { FormEvent, useState } from "react";

import { CallRegistration, registerCall } from "../../api/calls";

export function CallUploadForm() {
  const [result, setResult] = useState<CallRegistration | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setResult(null);
    setIsSubmitting(true);

    try {
      const registration = await registerCall(
        new FormData(event.currentTarget),
      );
      setResult(registration);
      event.currentTarget.reset();
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

  return (
    <section className="upload-card" aria-labelledby="upload-title">
      <div>
        <p className="eyebrow">New call</p>
        <h2 id="upload-title">Register a call for review</h2>
        <p className="supporting-copy">
          Upload an MP3 or WAV recording with its Call Radar JSON metadata.
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
            required
            type="file"
          />
          <span className="field-hint">
            The JSON supplies the agent and caller names automatically.
          </span>
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
        <p className="form-success" role="status">
          Call registered. Processing status: <strong>{result.status}</strong>.
        </p>
      ) : null}
    </section>
  );
}
