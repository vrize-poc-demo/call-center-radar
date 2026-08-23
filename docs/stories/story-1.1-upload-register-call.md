# Story 1.1: Upload and Register Call

**GitHub issue:** [#16](https://github.com/vrize-poc-demo/call-center-radar/issues/16)

**Status:** In Progress

**Owner:** Susmitha

**Epic:** Call intake and processing pipeline
**Last updated:** 2026-08-21

## 1. Outcome

### User-Visible Goal

A manager can upload a supported call recording and its Call Radar metadata, then immediately see that the call was registered with a queued processing job.

### Scope

- Included: MP3/WAV and Call Radar JSON metadata upload form, API validation, local generated-name audio/metadata storage, call and queued-job persistence, safe registration logs, immediate UI status, and focused tests.
- Excluded: audio inspection, transcription, speaker detection, job execution, retries, job-event history, transcript persistence, and AI analysis.

### Acceptance Criteria

- [x] A supported audio file can be uploaded with the required metadata.
- [x] The system creates linked call and processing job records.
- [x] The UI shows the initial job status immediately after submission.

## 2. Design

### Flow

```mermaid
flowchart LR
  U[Manager selects MP3/WAV and JSON] --> F[React upload form]
  F --> A[POST /api/calls]
  A --> V[Validate extension, size, and required fields]
  V --> S[Generated local audio path]
  S --> C[(calls)]
  C --> J[(processing_jobs: queued)]
  J --> R[UI displays queued]
```

### Components and Ownership

| Area | Files or module | Responsibility |
| --- | --- | --- |
| UI | `apps/web/src/features/calls/CallUploadForm.tsx` | Captures audio and Call Radar JSON metadata; displays queued or validation error state. |
| Web API client | `apps/web/src/api/calls.ts` | Sends multipart data and exposes a typed registration response. |
| API | `apps/api/src/app/calls.py` | Validates and registers the upload without starting processing. |
| Persistence | `migrations/002_upload_jobs.sql` | Adds the minimal linked `processing_jobs` record. |
| Configuration | `config.py`, `.env.example` | Defines local upload directory and maximum upload size. |
| Tests | `apps/api/tests/test_calls.py` | Covers successful registration and safe rejection paths. |

### Contracts and Data

`POST /api/calls` accepts `audio`, editable `agent_name`/`customer_name`, and optional `metadata`. A `.json` Call Radar export containing `agent.metadata.agent_name` and `caller.metadata["first and last name"]` fills the UI fields and becomes the submitted source when present. Without metadata, the entered names are required. It returns HTTP 201 with generated `call_id`, `job_id`, and `status: "queued"`. The service accepts `.mp3` and `.wav` files and an optional JSON metadata file up to `CALL_RADAR_MAX_UPLOAD_BYTES`, stores files under generated IDs, and records either the metadata path or a `manual://` source marker in `source_metadata_path`.

## 3. Operational Behavior

### Logging and Privacy

Events are `call_upload_received`, `call_upload_rejected`, and `call_registered`. Registration logs contain only technical IDs and validation status codes. They exclude original filenames, audio bytes, agent/customer names, and other PII.

### Failure and Recovery

Unsupported, empty, oversized, or malformed metadata files return a clear 4xx response and create no database records. If persistence fails after files are written, both generated local files are removed before the error is propagated. Orphaned files after a process crash can be removed manually from the ignored upload directory. Story 1.2 owns retries and durable job events.

## 4. Verification

### Automated Tests

| Check | Result | Notes |
| --- | --- | --- |
| API happy-path registration | Passed | Verifies call, queued job, and generated audio storage are linked. |
| Unsupported-file validation | Passed | Verifies no records are created. |
| Size-limit validation | Passed | Verifies no call record is created. |
| Existing API workflow tests | Passed | Migration and health behavior remain valid. |
| API lint and format | Passed | Ruff check and format check passed. |
| Web lint, test, and build | Passed | ESLint, Vitest, and Vite production build passed. |
| Accuracy evaluation | Not applicable | This story does not make an AI judgment. |

### Manual Verification and Demo Path

1. Start the web and API services.
2. Upload a short MP3 or WAV. Enter agent/customer names manually, or choose its paired JSON file from `sample-data/callradar-data/metadata` to fill those fields.
3. Show the immediate `Queued` status.
4. Inspect the SQLite call and processing-job records without exposing call content.

### Known Gaps and Follow-Up Boundaries

- Story 1.2 owns actual processing lifecycle states, audio validation, channel detection, and job events.
- Story 1.3 owns transcript turns and immutable evidence IDs.
- The extension check is intentionally lightweight; deep audio decoding belongs to Story 1.2.
- Local audio upload files are ignored by Git and are not a production retention strategy.

## 5. Delivery Record

- Branch: `feature/story-1.1-upload-register-call`
- Pull request: [#46](https://github.com/vrize-poc-demo/call-center-radar/pull/46)
- Commit(s): `67f798e` plus pending metadata-upload update
- Review result: Pending

### Change Log

Update this table before every commit. Explain both the change and its reason; do not use generic entries such as "updates" or "fixes".

| Commit | What changed | Why |
| --- | --- | --- |
| 67f798e | Added the Story 1.1 registration flow, migration, UI, validation, tests, and delivery record. | Deliver the smallest end-to-end upload-to-queued-job slice while preserving the Story 1.2 processing boundary. |
| Pending | Replaced manual participant-name fields with Call Radar JSON metadata upload, extraction, storage, and validation. | The supplied dataset already provides authoritative agent and caller names, reducing manual entry errors. |
| Pending | Added editable manual participant names, optional metadata upload with automatic UI population, and a safe form reset after submission. | Support both intake workflows and prevent the post-upload form-reset error. |

### PR Readiness and Review

- Mergeability verification: Pending - `npm run pr:verify -- <pr-number>`
- Code quality grade: Pending - A to F
- Testing quality grade: Pending - A to F
- Review findings and follow-up: Pending full local quality-gate results.
