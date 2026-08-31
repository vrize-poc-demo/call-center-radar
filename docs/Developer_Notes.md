# Developer Documentation

This is the project-level guide for engineering work on the Call Center Radar POC. It deliberately does not hold individual implementation histories. Every implemented story has its own complete record in [`docs/stories`](stories/README.md), kept with the code and reviewed in the same pull request.

## Documentation Rule

One GitHub story must have one file at `docs/stories/story-x.y-short-name.md`.

Create the story file when implementation starts, update it as the design changes, and complete every section before the pull request moves to review. Start from [`_template.md`](stories/_template.md). The story document is part of the definition of done, alongside code, tests, logs, and the PR description.

The record must state:

- The manager or operational outcome and intentionally excluded scope.
- The implementation flow and component boundaries, with a simple diagram when it clarifies the design.
- Changed UI, API, database, configuration, and files.
- Logging, redaction, failure behavior, and recovery behavior.
- Automated tests, manual verification, known gaps, and acceptance result.
- A short demo path and the next story boundaries.

## Implemented Stories

| Story | Record | Status |
| --- | --- | --- |
| 0.1 | [Monorepo and app bootstrap](stories/story-0.1-monorepo-and-app-bootstrap.md) | Merged |
| 0.2 | [Core developer workflow](stories/story-0.2-core-developer-workflow.md) | Merged |
| 0.3 | [CI baseline](stories/story-0.3-ci-baseline.md) | In review |
| 1.1 | [Upload and register call](stories/story-1.1-upload-register-call.md) | In progress |

## Common Setup

Prerequisites: Node 20.15+ with npm 10.7+, and Python 3.12+.

```bash
npm install
python3 -m venv .venv
./.venv/bin/pip install -e 'apps/api[dev]'
cp .env.example .env
npm run dev
```

The manager UI runs at `http://localhost:5173`. The API runs at `http://localhost:8000/api`.
`npm run dev` is the single runner for both services and is cross-platform on macOS, Linux, and
Windows when `./.venv` is present. It also starts the local Ollama analysis service when Ollama is
installed on `PATH`, verifies the configured model, and pulls the model once if it is missing.

Useful local AI overrides:

- `CALL_RADAR_START_OLLAMA=false npm run dev` starts only the app services.
- `CALL_RADAR_PULL_OLLAMA_MODEL=false npm run dev` fails fast if the configured model is missing.
- `CALL_RADAR_OLLAMA_MODEL=<model> npm run dev` changes the local structured-analysis model.

Run the pull-request quality gate before requesting review:

```bash
npm run lint
npm run format:check
npm run test:coverage
npm run build
```

Optionally install local commit checks after setup:

```bash
npm run precommit:install
```

## Engineering Rules

- Keep stories vertical: UI, API, persistence, logging, and tests travel together whenever a user-visible outcome needs them.
- Keep product logic in feature modules, not in route handlers or React page components.
- Treat saved transcript turns as immutable evidence. AI output may reference a `transcript_turn_id`; it may not invent a timestamp or quote.
- SQLite is the only POC database. Schema changes require a versioned migration and a documented rollback or recovery note.
- Do not call paid AI services from default development or demo flows. Provider integrations must remain behind an interface.
- Do not log raw audio, customer PII, access tokens, or full transcripts unless an explicit later story defines redaction and retention.
- Start from updated `development`, use a focused `feature/story-x.y-description` branch, and merge through a PR into `development`.

Project scope, architecture, and delivery order remain in [`Implementation_Backlog_Plan.md`](Implementation_Backlog_Plan.md) and the [wiki documents](wiki/Home.md).
Model, library, database, queue, and framework tradeoffs are recorded in [`Technology_Decisions.md`](Technology_Decisions.md), including pros, cons, free POC defaults, and upgrade paths for better accuracy or production readiness.

All contributors must follow [`Engineering_Governance.md`](Engineering_Governance.md). Coding agents must also follow the repository-level instructions in [`AGENTS.md`](../AGENTS.md).
