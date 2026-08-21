# Story Documentation

This directory is the code-adjacent engineering record for the Call Center Radar POC. Each GitHub story must have exactly one Markdown document here. The document is updated in the same branch and pull request as its implementation, so a reviewer can verify intent, behavior, evidence, tests, and operational decisions together.

## Naming

Use `story-x.y-short-name.md`, for example `story-2.2-audio-transcript-sync.md`.

## Required Completion Checklist

- [ ] Goal, user-visible outcome, scope, and non-goals are explicit.
- [ ] Architecture and execution flow are explained; add a small Mermaid diagram where useful.
- [ ] Code ownership, API, persistence, and configuration changes are recorded.
- [ ] Logging, redaction, failure behavior, and recovery behavior are recorded.
- [ ] Automated tests, manual checks, results, and known gaps are recorded.
- [ ] Acceptance criteria are checked against the story issue.
- [ ] The demo path, PR, and next-story boundaries are recorded.

Copy [`_template.md`](_template.md) at the start of every new story. Do not delete sections that do not apply; mark them `Not applicable` and state why.

## Story Records

| Story | Record |
| --- | --- |
| 0.1 | [Monorepo and app bootstrap](story-0.1-monorepo-and-app-bootstrap.md) |
| 0.2 | [Core developer workflow](story-0.2-core-developer-workflow.md) |
| 0.3 | [CI baseline](story-0.3-ci-baseline.md) |
