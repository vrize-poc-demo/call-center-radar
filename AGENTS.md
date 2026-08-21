# Codex Repository Rules

These instructions are mandatory for Codex and any coding agent working in this repository. They supplement the developer workflow in [`docs/Engineering_Governance.md`](docs/Engineering_Governance.md).

## Authority Boundary

- Codex may create branches, commits on feature or hotfix branches, issues, project-status updates, draft pull requests, and PR review comments.
- Codex must never commit or push directly to `development` or `main`.
- Codex must never merge, enable auto-merge, approve its own PR, delete another developer's branch, or alter branch-protection settings.
- A human repository maintainer is the only authority that merges a PR into `development`.

## Required Story Flow

1. Read the story issue and its parent epic. Keep the work limited to that story's acceptance criteria.
2. Inspect the worktree. Do not stage, revert, or overwrite unrelated user changes.
3. Fetch `origin/development`, then create a new `feature/story-x.y-short-name` branch from `origin/development`. Never branch a new story from an old feature branch.
4. Assign the story as agreed and move its GitHub Project item to `In Progress` before implementation.
5. Create or update exactly one `docs/stories/story-x.y-short-name.md` record from the template.
6. Make small, focused commits on the feature branch only. Before every commit, update that story record's change log with what changed and why.
7. Run focused tests and the full quality gate relevant to the change. Record commands, result, coverage where relevant, gaps, and manual verification in the story document.
8. Push the feature branch and create a draft PR with base branch `development`. Never target `main` unless a human explicitly requests a release PR.
9. Review the PR code and tests using the A-F rubric in the PR template. Record the grade and findings in the PR body.
10. Run `npm run pr:verify -- <pr-number>`. Do not move the story to `In Review` until the PR targets `development`, GitHub reports it cleanly mergeable, and all checks pass.
11. Move the story to `In Review`, then wait for human review and merge. Do not change it to `Done` until a human merge is confirmed.

## Documentation Standard

The story record is required for every code, configuration, test, or documentation change. It must explain the outcome, scope, design, changed files and contracts, data handling, logging and privacy, failure/recovery behavior, tests, acceptance result, demo path, known gaps, and delivery history.

Use [`docs/stories/_template.md`](docs/stories/_template.md). Never remove a template section because it seems irrelevant; state `Not applicable` and explain why.
