# Architecture and Delivery Plan

## System Architecture

```mermaid
flowchart LR
  A[Upload Audio] --> B[Call Record + Job]
  B --> C[Audio Validation]
  C --> D[Transcription]
  D --> E[Transcript Turns with Immutable IDs]
  E --> F[Evidence Engine]
  F --> G[Structured LLM Analysis]
  G --> H[Validation Layer]
  H --> I[Analysis Store in SQLite]
  I --> J[Manager Dashboard]
  I --> K[Call Detail]
  I --> L[Issue Radar]
  I --> M[Customer Journey]
  I --> N[Agent Experience]
```

## Call Detail Proof Flow

```mermaid
flowchart TD
  A[Manager opens call] --> B[Reads Manager Brief]
  B --> C[Views Radar Priority]
  C --> D[Opens Score Breakdown]
  D --> E[Clicks Show Me Why]
  E --> F[Evidence Drawer Opens]
  F --> G[Transcript Turn Highlighted]
  G --> H[Audio Jumps to Timestamp]
```

## Two-Person Delivery Strategy

```mermaid
flowchart TD
  S[Initial Setup by Person A] --> P1[Phase 1]
  P1 --> A1[Person A: Intake + Pipeline]
  P1 --> B1[Person B: Call Detail]
  A1 --> P2[Phase 2]
  B1 --> P2
  P2 --> A2[Person A: Evidence + AI + Validator]
  P2 --> B2[Person B: Dashboard]
  A2 --> P3[Phase 3]
  B2 --> P3
  P3 --> A3[Person A: Score + Explainability + Logs]
  P3 --> B3[Person B: Quality Signals]
  A3 --> P4[Phase 4 Stretch]
  B3 --> P4
  P4 --> A4[Person A: Issue Radar]
  P4 --> B4[Person B: Customer Journey]
  A4 --> P5[Phase 5]
  B4 --> P5
  P5 --> Z[Joint Testing + Accuracy Checks + Demo Hardening]
```

## Delivery Priority Roadmap

```mermaid
flowchart LR
  F0[Foundation] --> F1[Intake]
  F1 --> F2[Call Detail]
  F2 --> F3[AI Analysis]
  F3 --> F4[Radar Priority]
  F4 --> F5[Dashboard]
  F5 --> F6[Quality Signals]
  F6 --> F7[Issue Radar]
  F6 --> F8[Customer Journey]
  F8 --> F9[Agent Experience]
  F9 --> F10[Testing + Demo Readiness]
```

## Epic Backlog

1. Foundation and developer workflow
2. Call intake and processing pipeline
3. Call Detail core experience
4. Evidence-backed AI analysis
5. Radar Priority and Show Me Why
6. Manager dashboard
7. Quality signals
8. Issue Radar
9. Customer Journey
10. Agent experience
11. Observability, testing, and accuracy
12. Demo readiness

## Must-Have POC Scope

The must-have slice for a short POC delivery is:

1. Setup
2. Upload and job pipeline
3. Call Detail with audio/transcript sync
4. Evidence-backed intent, mood, resolution, and summary
5. Manager brief and recommended action
6. Radar Priority and score breakdown
7. Ranked dashboard queue
8. Logs, basic tests, and fallback demo flow

## Definition of Done

Every implementation story should include:

- UI
- API or backend behavior
- Persistence where needed
- Logging
- Tests
- Acceptance checks
- Demo-ready state
