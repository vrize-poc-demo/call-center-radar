import { ChangeEvent, FormEvent, useMemo, useState } from "react";

import {
  clearAllCallData,
  CallRegistration,
  processCall,
  ProcessingStatus,
  registerCall,
} from "../../api/calls";

type BatchFileGroup = {
  stem: string;
  audioFile?: File;
  metadataFile?: File;
};

function fileStem(file: File) {
  return file.name.replace(/\.[^.]+$/, "");
}

export function CallUploadForm() {
  const [result, setResult] = useState<CallRegistration | null>(null);
  const [processingResult, setProcessingResult] =
    useState<ProcessingStatus | null>(null);
  const [batchResults, setBatchResults] = useState<CallRegistration[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [agentName, setAgentName] = useState("");
  const [customerName, setCustomerName] = useState("");
  const [audioFiles, setAudioFiles] = useState<File[]>([]);
  const [metadataFiles, setMetadataFiles] = useState<File[]>([]);
  const [folderFiles, setFolderFiles] = useState<File[]>([]);

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

  function groupSelectedFiles(files: File[]) {
    const groups = new Map<string, BatchFileGroup>();
    for (const file of files) {
      const stem = fileStem(file);
      const entry = groups.get(stem) ?? { stem };
      if (file.type.startsWith("audio/") || /\.(mp3|wav)$/i.test(file.name)) {
        entry.audioFile = file;
      } else if (file.name.toLowerCase().endsWith(".json")) {
        entry.metadataFile = file;
      }
      groups.set(stem, entry);
    }
    return [...groups.values()];
  }

  const folderPairs = useMemo(
    () => groupSelectedFiles(folderFiles),
    [folderFiles],
  );

  async function handleBatchSubmit() {
    if (!folderPairs.length && !audioFiles.length) {
      setError("Select at least one audio file or folder to upload.");
      return;
    }

    setError(null);
    setStatusMessage("Preparing batch upload...");
    setBatchResults([]);
    setResult(null);
    setProcessingResult(null);
    setIsSubmitting(true);

    const uploaded: CallRegistration[] = [];

    try {
      const entries = folderPairs.length
        ? folderPairs
        : audioFiles.map((audioFile) => {
            const metadataFile = metadataFiles.find(
              (file) => fileStem(file) === fileStem(audioFile),
            );
            return { stem: fileStem(audioFile), audioFile, metadataFile };
          });

      for (const entry of entries) {
        if (!entry.audioFile) {
          continue;
        }

        const formData = new FormData();
        formData.append("audio", entry.audioFile);

        if (entry.metadataFile) {
          formData.append("metadata", entry.metadataFile);
        } else {
          const inferredAgent = agentName.trim();
          const inferredCustomer = customerName.trim();
          if (!inferredAgent || !inferredCustomer) {
            throw new Error(
              `Missing metadata for ${entry.stem}. Provide a JSON file or fill in the participant names.`,
            );
          }
          formData.append("agent_name", inferredAgent);
          formData.append("customer_name", inferredCustomer);
        }

        const registration = await registerCall(formData);
        uploaded.push(registration);
        setStatusMessage(
          `Registered ${uploaded.length} call${uploaded.length === 1 ? "" : "s"}...`,
        );
        await processCall(registration.job_id);
      }

      setBatchResults(uploaded);
      setStatusMessage(
        `Registered and queued ${uploaded.length} call${uploaded.length === 1 ? "" : "s"}.`,
      );
      setAudioFiles([]);
      setMetadataFiles([]);
      setFolderFiles([]);
      setAgentName("");
      setCustomerName("");
    } catch (submissionError) {
      setError(
        submissionError instanceof Error
          ? submissionError.message
          : "The batch could not be registered.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleClearAll() {
    setIsClearing(true);
    setError(null);
    setStatusMessage(null);
    try {
      const cleared = await clearAllCallData();
      setResult(null);
      setProcessingResult(null);
      setBatchResults([]);
      setAudioFiles([]);
      setMetadataFiles([]);
      setFolderFiles([]);
      setAgentName("");
      setCustomerName("");
      setStatusMessage(
        `Cleared ${cleared.calls_deleted} stored call${cleared.calls_deleted === 1 ? "" : "s"} and removed ${cleared.upload_files_deleted} uploaded file${cleared.upload_files_deleted === 1 ? "" : "s"}.`,
      );
    } catch (clearError) {
      setError(
        clearError instanceof Error
          ? clearError.message
          : "Stored call data could not be cleared.",
      );
    } finally {
      setIsClearing(false);
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
      setProcessingResult(await processCall(registration.job_id));
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
        <div className="upload-hint-block">
          <p className="field-hint">
            Batch import: select multiple audio files, multiple metadata files,
            or a whole folder of paired sample files.
          </p>
        </div>
        <label>
          Audio files
          <input
            accept="audio/mpeg,audio/wav,.mp3,.wav"
            multiple
            onChange={(event) =>
              setAudioFiles([...(event.currentTarget.files ?? [])])
            }
            type="file"
          />
        </label>
        <label>
          Metadata files
          <input
            accept="application/json,.json"
            multiple
            onChange={(event) =>
              setMetadataFiles([...(event.currentTarget.files ?? [])])
            }
            type="file"
          />
        </label>
        <label>
          Sample folder
          <input
            // @ts-expect-error webkitdirectory is supported in Chromium-based browsers.
            webkitdirectory=""
            multiple
            onChange={(event) =>
              setFolderFiles([...(event.currentTarget.files ?? [])])
            }
            type="file"
          />
          <span className="field-hint">
            Pick the sample-data folder to import every matching audio and JSON
            file in one step.
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
        <div className="upload-form-actions">
          <button disabled={isSubmitting} type="submit">
            {isSubmitting ? "Registering…" : "Register call"}
          </button>
          <button
            disabled={isSubmitting}
            onClick={() => void handleBatchSubmit()}
            type="button"
          >
            {isSubmitting ? "Uploading…" : "Upload batch"}
          </button>
          <button
            disabled={isClearing}
            onClick={() => void handleClearAll()}
            type="button"
          >
            {isClearing ? "Clearing…" : "Clear all data"}
          </button>
        </div>
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
                ? `Transcribed ${processingResult.transcript_turn_count} saved turns from ${processingResult.audio_channels === 1 ? "mono" : "stereo"} audio.`
                : processingResult.status === "failed"
                  ? `Processing failed: ${processingResult.failure_reason}.`
                  : "Processing has started. You can register another call or keep navigating while it runs."}
            </p>
          ) : null}
          <div className="processing-actions">
            <a href={`?call=${result.call_id}`}>Open call detail</a>
          </div>
        </div>
      ) : null}
      {batchResults.length ? (
        <div className="batch-results" role="status">
          <p className="form-success">
            Uploaded {batchResults.length} call
            {batchResults.length === 1 ? "" : "s"}.
          </p>
          <ul>
            {batchResults.map((item) => (
              <li key={item.call_id}>{item.call_id} queued for processing</li>
            ))}
          </ul>
        </div>
      ) : null}
      {statusMessage ? <p className="field-hint">{statusMessage}</p> : null}
    </section>
  );
}
