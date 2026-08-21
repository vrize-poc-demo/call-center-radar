## Story

- GitHub issue: Closes #
- Project status: `In Progress` -> `In Review`
- Story document: `docs/stories/story-x.y-short-name.md`

## What Changed and Why

Describe the user-visible or developer-visible outcome, the implementation change, and why this is the smallest correct change for the story.

## Scope and Risk

- Included:
- Explicitly excluded:
- Risk and rollback or recovery:
- Logging, privacy, and data-handling impact:

## Verification

- [ ] `npm run lint`
- [ ] `npm run format:check`
- [ ] `npm run test:coverage`
- [ ] `npm run build`
- [ ] Focused manual verification completed and recorded in the story document.
- [ ] GitHub Actions `Quality gates` passed on this PR.
- [ ] `npm run pr:verify -- <pr-number>` passed.

## Self-Review Grade

Use the A-F rubric in `docs/Engineering_Governance.md`. A coding agent may assess this PR but must never self-approve or merge it.

- Code quality: `A | B | C | D | E | F`
- Testing quality: `A | B | C | D | E | F`
- Findings and follow-up actions:

## Documentation

- [ ] The story document explains every committed change and why it was made.
- [ ] The story document records API, database, configuration, logging, privacy, test, acceptance, demo, and known-gap impacts or marks them not applicable.
- [ ] The delivery record contains the branch, PR, and commits.

## Merge Authority

- [ ] Base branch is `development`.
- [ ] This PR is for human review and merge only. No coding agent may merge or enable auto-merge.
