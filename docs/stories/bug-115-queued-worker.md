# Bug 115: Processing queue remains stuck in Queued state

**GitHub issue:** #115

**Status:** In Progress

**Owner:** SusmithaKM / Codex

**Epic:** Operational reliability
**Last updated:** 2026-08-28

## 1. Outcome

### User-Visible Goal

Registered calls should automatically enter the durable local processing worker after upload. Managers should not see calls remain in `Queued` indefinitely just because the frontend did not successfully send a second processing-start request.

### Scope

- Included:
  - Wake the durable processing worker from the backend registration endpoint immediately after the job row is created.
  - Preserve the existing explicit `POST /api/calls/{job_id}/process` endpoint as an idempotent compatibility fallback.
  - Add regression coverage proving registration enqueues the worker without an extra process request.
  - Log an actionable enqueue failure if the newly created job cannot be found by the worker.
- Excluded:
  - Changing transcription quality, Ollama analysis, or dashboard scoring behavior.
  - Changing the public registration response shape.
  - Adding a separate worker-health dashboard.

### Acceptance Criteria

- [x] Reproduce and identify why queued jobs are not reliably being picked up after registration.
- [x] Add code-level guard so call registration wakes the processing worker directly.
- [x] Ensure registered jobs no longer depend on a frontend-only second request to begin processing.
- [x] Add regression coverage for the stuck-queued scenario.
- [x] Update docs/story notes with final verification and PR details.

## 2. Design

### Flow

```mermaid
flowchart LR
  A[POST /api/calls] --> B[Persist call and queued job]
  B --> C[Backend calls processing_worker.enqueue(job_id)]
  C --> D[Worker wake event set]
  D --> E[Worker claims queued job FIFO]
```

### Components and Ownership

| Area | Files or module | Responsibility |
| --- | --- | --- |
| UI | Not applicable | Existing frontend can still call the process endpoint, but backend registration no longer depends on it. |
| API | `apps/api/src/app/calls.py` | Wake the durable worker after successful call/job registration. |
| Persistence | `processing_jobs` | No schema change; existing queued job row is used. |
| Tests | `apps/api/tests/test_calls.py` | Verify registration invokes worker enqueue directly. |

### Contracts and Data

No API request or response shape changed. No database migration is required. The registration endpoint still returns `status: "queued"` because processing remains asynchronous, but it now also wakes the local worker server-side.

## 3. Operational Behavior

### Logging and Privacy

Existing `processing_enqueued` logging records job ID, job status, and queue depth. The new `processing_enqueue_failed` event logs only call ID and job ID if the freshly registered job cannot be enqueued. Logs do not include raw audio, full transcripts, uploaded metadata content, customer names, or secrets.

### Failure and Recovery

If the worker cannot find the job that was just created, registration returns a server error with a stable message. Existing uploaded files and records remain available for developer diagnosis. Normal transcription failures still move the job to `failed` with the existing stable failure reasons.

## 4. Verification

### Automated Tests

| Check | Result | Notes |
| --- | --- | --- |
| Unit tests | Passed | `$env:PYTHONPATH = "$PWD\apps\api\src"; C:\Hack-Projects\call-center-radar\.venv\Scripts\python.exe -m pytest apps\api\tests\test_calls.py apps\api\tests\test_pipeline.py` -> 21 passed, 1 warning. |
| Integration tests | Passed | Focused registration and durable queue tests cover the backend worker wake path and existing process endpoint behavior. |
| Lint and format | Passed | `python -m ruff check apps\api\src\app\calls.py apps\api\tests\test_calls.py`; `python -m ruff format --check apps\api\src\app\calls.py apps\api\tests\test_calls.py`. |
| Build | Not applicable | API-only queue wake fix. |
| Accuracy evaluation | Not applicable | No analysis model or scoring logic changed. |

### Manual Verification and Demo Path

1. Start the API and web app from latest development plus this branch.
2. Register one or more valid audio calls.
3. Confirm the Recent calls panel moves jobs out of `Queued` without waiting for a separate manual processing action.
4. Confirm the queue eventually shows `Completed` or `Failed` instead of staying `Queued`.

### Known Gaps and Follow-Up Boundaries

- If the transcription model itself is slow or unavailable, jobs may still take time after moving to `transcribing`.
- A future enhancement can expose worker heartbeat/health in `/api/health` or the queue UI.

## 5. Delivery Record

- Branch: `feature/bug-115-queued-worker`
- Pull request: https://github.com/vrize-poc-demo/call-center-radar/pull/116
- Commit(s): `ddc1721`
- Review result: TBD

### Change Log

Update this table before every commit. Explain both the change and its reason; do not use generic entries such as "updates" or "fixes".

| Commit | What changed | Why |
| --- | --- | --- |
| `ddc1721` | Backend registration now wakes the durable processing worker and focused tests cover the behavior. | Prevent calls from remaining queued when the frontend process-start request is missed or delayed. |

### PR Readiness and Review

- Mergeability verification: `Blocked locally - npm run pr:verify -- 116 could not run because bash is not on PowerShell PATH; Git Bash retry reached the script but failed because GitHub CLI (gh) is not installed.`
- Code quality grade: `A`
- Testing quality grade: `A`
- Review findings and follow-up: No known blocking issues. Install GitHub CLI locally to run the repository PR verification script end-to-end.
