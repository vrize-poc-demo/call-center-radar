# Call Center Radar

Call Center Radar is an evidence-first call intelligence POC for support and operations teams. It processes call recordings, creates structured transcripts, and shows manager-ready insights with traceable evidence.

## What You Need

Before you run the project, make sure you have:

1. Node.js 20 or newer
2. npm 10 or newer
3. Python 3.11 or newer
4. A local Python virtual environment at `./.venv`
5. The repository dependencies installed

You will also need the sample data if you want to try the demo flow:

- `sample-data/callradar-data/audio/`
- `sample-data/callradar-data/metadata/`

## Install

From the repository root:

```bash
npm install
```

If the Python environment is not already created, create and activate it first, then install the API dependencies used by the project.

## Run Locally

Start both the web app and the API together:

```bash
npm run dev
```

That starts:

- the web app on Vite
- the API server on `http://127.0.0.1:8000`

If you want to run them separately:

```bash
npm run dev:web
```

```bash
npm run dev:api
```

## Build

To build the web app:

```bash
npm run build
```

## Test

Run the full test suite:

```bash
npm run test
```

Run lint checks:

```bash
npm run lint
```

Run formatting checks:

```bash
npm run format:check
```

## Database Setup

The POC uses SQLite.

If you need to prepare or seed the local database, use:

```bash
npm run db:migrate
```

```bash
npm run db:seed
```

## Demo Flow

The intended demo flow is:

1. Open the app in the browser
2. Upload a call recording
3. Watch the processing job complete
4. Open the Call Detail page
5. Review the transcript, evidence, and manager recommendations
6. Jump between evidence and audio timestamps

## Project Focus

This repo is built around three POC goals:

- Trust: every important AI judgment must point back to saved transcript evidence
- Speed: new recordings can be processed during the demo
- Action: managers get a clear brief, a score, and a recommended next step

## Helpful Docs

- [Engineering Governance](docs/Engineering_Governance.md)
- [Git Flow](docs/Git_Flow.md)
- [Implementation Backlog Plan](docs/Implementation_Backlog_Plan.md)
- [Wiki Home](docs/wiki/Home.md)
