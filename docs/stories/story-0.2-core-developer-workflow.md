# Story 0.2: Core Developer Workflow

**GitHub issue:** [#14](https://github.com/vrize-poc-demo/call-center-radar/issues/14)

**Status:** Done

**Owner:** Vipin

**Epic:** Foundation and developer workflow
**Last updated:** 2026-08-21

## 1. Outcome

### User-Visible Goal

Make local POC state repeatable for any contributor. A developer can initialize SQLite, apply versioned schema changes, seed safe sample metadata, inspect service health, and diagnose lifecycle activity without exposing audio or customer content.

### Scope

- Included: SQLite bootstrap, SQL migrations, metadata-only seed command, JSON lifecycle logs, health endpoint, local configuration, and run documentation.
- Excluded: uploaded audio persistence, transcript turns, customer journey data, job queue processing, and AI analysis.

### Acceptance Criteria

- [x] SQLite is initialized through a versioned, idempotent migration path.
- [x] Safe sample metadata can be seeded without copying or reading audio.
- [x] The API reports a clear health state and database reachability.
- [x] Lifecycle events are logged without sensitive call content.

## 2. Design

### Flow

```mermaid
flowchart LR
  D[Developer] --> C[CLI command]
  C --> M[Versioned migration]
  M --> S[(SQLite)]
  C --> Seed[Metadata-only seed]
  Seed --> S
  B[Manager browser] --> H[/api/health]
  H --> S
  C --> L[JSON lifecycle logs]
```

### Components and Ownership

| Area | Files or module | Responsibility |
| --- | --- | --- |
| API | `apps/api/src/app/main.py` | Application creation and health routes. |
| Configuration | `apps/api/src/app/config.py` | Local database and sample-data locations. |
| Persistence | `database.py`, `migrator.py`, `migrations/001_initial.sql` | SQLite connections and ordered schema migrations. |
| Seed path | `seed.py`, `cli.py` | Metadata-only sample seeding and CLI commands. |
| Observability | `logging.py` | JSON-safe lifecycle event output. |
| Tests | `apps/api/tests/test_main.py`, `test_workflow.py` | Health, migration idempotence, and safe seeding tests. |

### Contracts and Data

Commands:

```bash
npm run db:migrate
npm run db:seed
curl http://127.0.0.1:8000/api/health
```

`/api/health` returns an operational status and database reachability only. The `calls` table stores sample metadata, but the seed process deliberately stores no audio path and does not read audio. The database location is configurable with `CALL_RADAR_DATABASE_PATH`; generated database files under `data/` remain untracked.

## 3. Operational Behavior

### Logging and Privacy

Lifecycle, migration, and seed events are emitted as JSON lines to standard output. They include technical operation context only. Raw audio, transcript text, customer names, customer identifiers, and access tokens are excluded.

### Failure and Recovery

Migration failure stops the command and leaves the applied-migration record intact. Re-running the migration command is idempotent. A developer can reset only their local ignored SQLite database when necessary, then rerun migration and seed commands. No reset command is supplied because deleting shared or demo data must be deliberate.

## 4. Verification

### Automated Tests

| Check | Result | Notes |
| --- | --- | --- |
| Migration tests | Passed | Verifies version ordering and idempotence. |
| Seed tests | Passed | Verifies metadata import does not read audio. |
| Health test | Passed | Verifies ready state and database reachability. |
| Lint, format, build | Passed | Root quality commands succeeded. |
| Accuracy evaluation | Not applicable | No analysis result is produced. |

### Manual Verification and Demo Path

1. Run `npm run db:migrate` and show the successful versioned migration.
2. Run `npm run db:seed` and show that only metadata records are added.
3. Start the application with `npm run dev`.
4. Open `/api/health` and show the `ok` and `reachable` response.
5. Point out the JSON lifecycle logs while confirming no call content is printed.

### Known Gaps and Follow-Up Boundaries

- Story 1.1 owns real uploaded-call registration and file references.
- Story 1.2 owns processing jobs and persistent status events.
- Story 1.3 owns immutable transcript turn storage.
- Story 0.3 owns the automated CI and coverage baseline for this workflow.

## 5. Delivery Record

- Branch: `feature/story-0.2-core-developer-workflow`
- Pull request: [#44](https://github.com/vrize-poc-demo/call-center-radar/pull/44)
- Commit(s): `8913aff`
- Review result: Merged into `development`
