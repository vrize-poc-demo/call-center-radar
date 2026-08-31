import { ChangeEvent, FormEvent, useMemo, useState } from "react";

import {
  clearAllCallData,
  CallRegistration,
  processCall,
  ProcessingStatus,
  registerCall,
} from "../../api/calls";

type BatchFileGroup = {
  key: string;
  audioFile?: File;
  metadataFile?: BatchMetadataFile;
};

type BatchMetadataFile = {
  file: File;
  key: string;
  error?: string;
};

type SkippedBatchFile = {
  name: string;
  reason: string;
};

function callFileKey(fileName: string) {
  return fileName
    .replace(/\.[^.]+$/, "")
    .replace(/\s+2$/, "")
    .trim();
}

function isAudioFile(file: File) {
  return /\.(mp3|wav)$/i.test(file.name);
}

function isMetadataFile(file: File) {
  return /\.json$/i.test(file.name);
}

function readFileText(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("File could not be read."));
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.readAsText(file);
  });
}

export function CallUploadForm() {
  const [activeTab, setActiveTab] = useState<"single" | "batch">("single");
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
  const [metadataFiles, setMetadataFiles] = useState<BatchMetadataFile[]>([]);

  async function populateNamesFromMetadata(
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const metadataFile = event.currentTarget.files?.[0];
    if (!metadataFile) return;

    try {
      const document = JSON.parse(await readFileText(metadataFile)) as {
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

  const batchPlan = useMemo(() => {
    const groups = new Map<string, BatchFileGroup>();
    const skipped: SkippedBatchFile[] = [];

    for (const audioFile of audioFiles) {
      if (!isAudioFile(audioFile)) {
        skipped.push({
          name: audioFile.name,
          reason: "unsupported audio type",
        });
        continue;
      }
      const key = callFileKey(audioFile.name);
      const entry = groups.get(key) ?? { key };
      if (entry.audioFile) {
        skipped.push({ name: audioFile.name, reason: "duplicate audio file" });
        continue;
      }
      entry.audioFile = audioFile;
      groups.set(key, entry);
    }

    for (const metadataFile of metadataFiles) {
      if (metadataFile.error) {
        skipped.push({
          name: metadataFile.file.name,
          reason: metadataFile.error,
        });
        continue;
      }
      if (!isMetadataFile(metadataFile.file)) {
        skipped.push({
          name: metadataFile.file.name,
          reason: "unsupported metadata type",
        });
        continue;
      }
      const entry = groups.get(metadataFile.key) ?? { key: metadataFile.key };
      if (entry.metadataFile) {
        skipped.push({
          name: metadataFile.file.name,
          reason: "duplicate metadata file",
        });
        continue;
      }
      entry.metadataFile = metadataFile;
      groups.set(metadataFile.key, entry);
    }

    const pairs: Required<
      Pick<BatchFileGroup, "audioFile" | "metadataFile">
    >[] = [];
    for (const entry of groups.values()) {
      if (entry.audioFile && entry.metadataFile) {
        pairs.push({
          audioFile: entry.audioFile,
          metadataFile: entry.metadataFile,
        });
      } else if (entry.audioFile) {
        skipped.push({
          name: entry.audioFile.name,
          reason: "matching metadata file was not selected",
        });
      } else if (entry.metadataFile) {
        skipped.push({
          name: entry.metadataFile.file.name,
          reason: "matching audio file was not selected",
        });
      }
    }

    return { pairs, skipped };
  }, [audioFiles, metadataFiles]);

  async function readBatchMetadataFiles(files: File[]) {
    const parsed = await Promise.all(
      files.map(async (file) => {
        try {
          const document = JSON.parse(await readFileText(file)) as {
            sid?: string;
          };
          const normalizedFileKey = callFileKey(file.name);
          const sid =
            typeof document.sid === "string" ? document.sid.trim() : "";
          if (sid && sid !== normalizedFileKey) {
            return {
              file,
              key: normalizedFileKey,
              error: "metadata sid does not match filename",
            };
          }
          return { file, key: sid || normalizedFileKey };
        } catch {
          return {
            file,
            key: callFileKey(file.name),
            error: "metadata JSON could not be read",
          };
        }
      }),
    );
    setMetadataFiles(parsed);
  }

  async function handleBatchSubmit() {
    if (!audioFiles.length && !metadataFiles.length) {
      setError("Select audio files and matching metadata files to upload.");
      return;
    }
    if (!batchPlan.pairs.length) {
      setError("No complete audio and metadata pairs were found.");
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
      for (const entry of batchPlan.pairs) {
        const formData = new FormData();
        formData.append("audio", entry.audioFile);
        formData.append("metadata", entry.metadataFile.file);

        const registration = await registerCall(formData);
        uploaded.push(registration);
        setStatusMessage(
          `Registered ${uploaded.length} call${uploaded.length === 1 ? "" : "s"}...`,
        );
        await processCall(registration.job_id);
      }

      setBatchResults(uploaded);
      setStatusMessage(
        `Registered and queued ${uploaded.length} call${uploaded.length === 1 ? "" : "s"}; skipped ${batchPlan.skipped.length}.`,
      );
      setAudioFiles([]);
      setMetadataFiles([]);
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

      <div className="upload-tabs" role="tablist" aria-label="Upload mode">
        <button
          aria-controls="single-call-upload-panel"
          aria-selected={activeTab === "single"}
          id="single-call-upload-tab"
          onClick={() => setActiveTab("single")}
          role="tab"
          type="button"
        >
          Single call upload
        </button>
        <button
          aria-controls="batch-upload-panel"
          aria-selected={activeTab === "batch"}
          id="batch-upload-tab"
          onClick={() => setActiveTab("batch")}
          role="tab"
          type="button"
        >
          Batch upload
        </button>
      </div>

      {activeTab === "single" ? (
        <form
          aria-labelledby="single-call-upload-tab"
          className="upload-form"
          id="single-call-upload-panel"
          onSubmit={handleSubmit}
          role="tabpanel"
        >
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
          <div className="upload-form-actions">
            <button disabled={isSubmitting} type="submit">
              {isSubmitting ? "Registering…" : "Register call"}
            </button>
            <button
              className="clear-data-button"
              disabled={isClearing}
              onClick={() => void handleClearAll()}
              type="button"
            >
              {isClearing ? "Clearing…" : "Clear all data"}
            </button>
          </div>
        </form>
      ) : (
        <div
          aria-labelledby="batch-upload-tab"
          className="upload-form"
          id="batch-upload-panel"
          role="tabpanel"
        >
          <div className="upload-hint-block">
            <p className="field-hint">
              Select multiple recordings and the matching JSON metadata files.
              Files are paired by metadata sid or normalized filename, for
              example <strong>call-1.wav</strong> with{" "}
              <strong>call-1.json</strong>.
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
                void readBatchMetadataFiles([
                  ...(event.currentTarget.files ?? []),
                ])
              }
              type="file"
            />
          </label>
          <p className="field-hint">
            Ready pairs: {batchPlan.pairs.length}. Skipped files:{" "}
            {batchPlan.skipped.length}.
          </p>
          {batchPlan.skipped.length ? (
            <div className="batch-skipped" role="status">
              <strong>Skipped before processing</strong>
              <ul>
                {batchPlan.skipped.slice(0, 8).map((item) => (
                  <li key={`${item.name}-${item.reason}`}>
                    {item.name}: {item.reason}
                  </li>
                ))}
              </ul>
              {batchPlan.skipped.length > 8 ? (
                <p className="field-hint">
                  {batchPlan.skipped.length - 8} more skipped files.
                </p>
              ) : null}
            </div>
          ) : null}
          <div className="upload-form-actions">
            <button
              disabled={isSubmitting}
              onClick={() => void handleBatchSubmit()}
              type="button"
            >
              {isSubmitting ? "Uploading…" : "Upload batch"}
            </button>
            <button
              className="clear-data-button"
              disabled={isClearing}
              onClick={() => void handleClearAll()}
              type="button"
            >
              {isClearing ? "Clearing…" : "Clear all data"}
            </button>
          </div>
        </div>
      )}

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
