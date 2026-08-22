# Story 3.9: Evidence-Backed Mood Timeline and Shift Points

**GitHub issue:** [#77](https://github.com/vrize-poc-demo/call-center-radar/issues/77)

**Status:** In Review

**Owner:** Vipin

**Epic:** Evidence-backed AI analysis
**Last updated:** 2026-08-22

## 1. Outcome

### User-Visible Goal

A manager can see a call's overall mood and open every detected mood change at
the exact saved transcript turn and audio moment that supports it. Calls with
no defensible change show an explicit no-shift state rather than a fabricated
timeline.

### Scope

- Included: persisted, ordered mood shifts; deterministic transcript-reference
  validation; local-demo shift detection; a small Call Detail timeline; and
  evidence/audio drill-down.
- Excluded: voice-tone emotion inference, cross-call trends, dense charts,
  psychological claims, and changes to dashboard aggregation.

### Acceptance Criteria

- [x] Analysis returns an overall mood and zero or more mood shifts.
- [x] Every shift includes a different source/target mood, reason, persisted
  turn ID, derived quote, and derived start/end timestamps.
- [x] Unsupported turn IDs, quotes, timestamps, same-state shifts, and
  out-of-order shifts are rejected before persistence.
- [x] Mood shifts are persisted separately from claims and reload with the
  existing analysis endpoint.
- [x] Call Detail shows each shift and jumps to matching transcript/audio.
- [x] Full quality gate passed; manual demo check and PR verification are pending.

## 2. Design

### Flow

```mermaid
flowchart LR
  T[Immutable transcript turns] --> M[Local model proposes mood shifts]
  M --> V[Deterministic turn-reference validator]
  V --> S[(SQLite mood shifts)]
  S --> D[Call Detail mood timeline]
  D --> A[Transcript and audio evidence]
```

### Components and Ownership

| Area | Files or module | Responsibility |
| --- | --- | --- |
| Analysis contract | `apps/api/src/app/analysis.py` | Propose, validate, persist, and load overall mood and shift events. |
| Evidence validation | `apps/api/src/app/validation.py` | Verify every mood-shift reference against immutable saved transcript turns. |
| Persistence | `apps/api/src/app/migrations/009_analysis_mood_shifts.sql` | Store ordered shift metadata linked to an analysis version. |
| Call Detail UI | `apps/web/src/features/call-detail/CallDetailPage.tsx` | Present simple timeline actions and evidence/audio jumps. |
| Tests | API analysis/validation/workflow and Call Detail suites | Protect persistence, rejection, ordering, and manager drill-down behavior. |

### Contracts and Data

`CallAnalysis` now includes `mood_shifts`: a maximum of six records with
`from_mood`, `to_mood`, `reason`, `transcript_turn_id`, `quote`, `start_ms`,
and `end_ms`. New SQLite table `call_analysis_mood_shifts` is owned by one
analysis record. Quotes and timestamps are not trusted from the model: they
must exactly match a saved transcript turn before persistence.

## 3. Operational Behavior

### Logging and Privacy

Successful analysis events include only analysis version, model version,
latency, and accepted shift count. Failed validation uses stable reason codes
and a rejected-shift indicator. Logs never include raw audio, transcript text,
quotes, customer or agent names, or secrets.

### Failure and Recovery

An invalid model shift fails the analysis response before it reaches SQLite;
the prior persisted analysis remains intact. A no-shift result is valid and
renders explanatory copy. Replacing transcript turns continues to invalidate
the parent analysis, including its dependent shift records through SQLite
cascade deletion.

## 4. Verification

### Automated Tests

| Check | Result | Notes |
| --- | --- | --- |
| Focused API tests | Passed | 14 analysis, validation, and migration-workflow tests passed. |
| Focused web tests | Passed | 15 Call Detail tests passed, including mood-shift audio jump. |
| Full unit tests | Passed | 26 web and 45 API tests passed through `npm run test:coverage`. |
| Lint and format | Passed | `npm run lint` and `npm run format:check` completed with no findings. |
| Build | Passed | `npm run build` completed the TypeScript and Vite production bundle. |
| Accuracy evaluation | Not applicable | Local demo heuristics are evidence-validated, not an accuracy claim. |

### Manual Verification and Demo Path

1. Upload or register a call with a saved problem turn followed by a supported
   recovery phrase.
2. Open Call Detail and locate the Mood timeline under Call analysis.
3. Select a shift and confirm the evidence drawer and audio player seek to its
   stored transcript timestamp.
4. Use a neutral-only call and confirm no mood-shift timeline is fabricated.

### Known Gaps and Follow-Up Boundaries

- The POC's local detector uses explicit transcript phrases; it does not infer
  emotion from voice tone.
- A later hosted/local LLM provider may improve proposed labels, but the
  transcript-reference validation contract remains mandatory.
- Issue Radar owns cross-call mood patterns and trends.

## 5. Delivery Record

- Branch: `feature/story-3.9-mood-timeline`
- Pull request: [#80](https://github.com/vrize-poc-demo/call-center-radar/pull/80)
  (draft, targets `development`)
- Commit(s): `a84388e` - mood shift persistence, validation, UI, tests, and delivery record.
- Review result: GitHub CI and `npm run pr:verify -- 80` passed; pending human
  review and merge.

### Change Log

| Commit | What changed | Why |
| --- | --- | --- |
| Pending | Added mood-shift persistence, validation, local-demo detection, Call Detail drill-down, tests, and this delivery record. | Make mood changes explainable at a real transcript/audio moment instead of relying on an opaque overall label. |
| Pending | Ran the complete automated test, lint, format, and production-build gate. | Confirm the new analysis contract and UI drill-down do not regress the POC. |
| Pending | Recorded PR #80, passing CI, mergeability verification, and the project review state. | Preserve a complete human-review handoff. |

### PR Readiness and Review

- Mergeability verification: Passed - `npm run pr:verify -- 80` confirmed a
  clean merge into `development` with passing GitHub CI.
- Code quality grade: A - validation and persistence reuse existing immutable
  transcript contracts; the UI stays a small evidence drill-down.
- Testing quality grade: A - API persistence/reload, evidence validation,
  invalid shifts, migration flow, UI drill-down, and the full gate are covered.
- Review findings and follow-up: No blocking findings. The local detector is a
  transparent POC heuristic; future model providers remain subject to the same
  deterministic validation.
