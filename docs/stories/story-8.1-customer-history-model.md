# Story 8.1: Customer history model

**GitHub issue:** #34

**Status:** In Progress

**Owner:** SusmithaKM

**Epic:** #9 Customer Journey

## 1. Outcome

Creates a deterministic, chronological, privacy-safe customer call-history read model for Story 8.2.

### Scope

- Included: normalized exact customer matching, history API, repeated issue markers, partial-analysis states, migration, and tests.
- Excluded: timeline UI, fuzzy identity matching, CRM profiles, and transcript search.

### Acceptance Criteria

- [x] Calls from the same customer form an ordered sequence.
- [x] Repeated issue history is exposed at the data-model level.
- [x] Matching remains POC-safe and deterministic.

## 2. Design

`customer_match_key` stores a normalized exact-name match key and is never returned or logged. `GET /api/calls/{call_id}/customer-history` orders matching calls by persisted `created_at`, exposes analysis availability, and marks repeated Issue Radar categories.

## 3. Operational Behavior

Logs `customer_history_loaded` with opaque call/count data and `customer_history_load_failed` on SQLite failure. No names, transcript text, or audio are logged.

## 4. Verification

| Check | Result | Notes |
| --- | --- | --- |
| Focused tests | Passed | 3 tests passed. |
| Ruff lint | Passed | `ruff check apps/api/src apps/api/tests`. |

## 5. Delivery Record

- Branch: `feature/story-8.1-customer-history-model`
- Pull request: TBD

### Change Log

| Commit | What changed | Why |
| --- | --- | --- |
| Pending | Added customer history schema, read model, logging, and tests. | Supplies the narrow, deterministic model required by #34. |
