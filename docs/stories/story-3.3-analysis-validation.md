# Story 3.3: Validation Layer

**GitHub issue:** [#24](https://github.com/vrize-poc-demo/call-center-radar/issues/24)

## Outcome

Only structured claims that exactly match a persisted transcript turn are returned. Unknown turn IDs, invented quotes, and altered timestamps are rejected with a logged reason.

## Verification

- Focused unit and integration suite: 7 passed.
- Five-call integration test creates five independent calls, saves distinct customer transcripts, requests analysis, and verifies each returned claim has the saved turn ID, exact quote, and persisted timestamp range.
- CI merge gate: the required `Quality gates` workflow runs web unit tests with coverage and API unit tests with coverage as separate steps before the build.

## Delivery Record

- Branch: `feature/story-3.3-analysis-validation`
- Pull request: [#54](https://github.com/vrize-poc-demo/call-center-radar/pull/54)
