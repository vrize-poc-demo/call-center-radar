# Engineering Governance

This policy applies to every contributor and coding agent working on Call Center Radar. It makes the two-person POC workflow predictable, reviewable, and safe for the demo timeline.

## Non-Negotiable Rules

| Rule | Required behavior |
| --- | --- |
| Protected integration branches | No direct commits or pushes to `development` or `main`. All changes reach them through a pull request. |
| New story start | Fetch `origin/development`, then create a new focused `feature/story-x.y-short-name` branch from it. Do not reuse an old story branch. |
| Project tracking | Assign the story and move it to `In Progress` before coding. Move it to `In Review` only after PR verification passes. A human moves it to `Done` after merge. |
| Documentation | Every story has one complete record in `docs/stories`. Update its change log before every commit, explaining what changed and why. |
| Merge authority | Coding agents may create PRs only. They must never merge, auto-merge, self-approve, or change branch protection. A human maintainer merges. |
| Pull-request readiness | Every PR targets `development`, has a clean merge state, and has passing required checks before review is requested. |
| Review grade | Every PR records a code-quality and test-quality grade from A to F using the rubric below. |

GitHub repository settings must protect `development` and `main` with pull requests and required `Quality gates` checks. This source-controlled policy explains the rule; GitHub branch protection enforces it.

## Story Start Procedure

```bash
git fetch origin development
git switch -c feature/story-1.1-upload-register-call origin/development
git push -u origin feature/story-1.1-upload-register-call
```

Then assign the GitHub issue and change its Project status to `In Progress`. Do not begin implementation from a stale feature branch, even when its code appears related. This protects the other contributor from accidental dependency and merge conflicts.

## Commit and Documentation Procedure

Before every commit:

1. Update `docs/stories/story-x.y-short-name.md`.
2. Add a change-log row describing the files or behavior changed and the reason for the change.
3. Update verification results when the change affects behavior, API, persistence, logging, or tests.
4. Stage only the story files. Never use `git add .`, `git add -A`, or `git add --all` in a mixed worktree.
5. Commit on the feature branch only.

The documentation is reviewed as part of the same PR as the code. A change without its explanation is incomplete.

## Pull Request Procedure

1. Run the local quality gate:

   ```bash
   npm run lint
   npm run format:check
   npm run test:coverage
   npm run build
   ```

2. Create a draft PR with base branch `development`.
3. Complete every section of [the PR template](../.github/pull_request_template.md), including the story-document link and A-F grade.
4. Wait for GitHub Actions to test the PR merge result.
5. Verify the PR:

   ```bash
   npm run pr:verify -- <pr-number>
   ```

6. If verification passes, set the Project item to `In Review`. Do not merge it. A human maintainer reviews and merges it.

The verifier fails when the PR has the wrong base branch, is not cleanly mergeable, has an incomplete check, has a failed check, or does not have a successful `Quality gates` check. GitHub Actions tests the pull-request merge ref, so a passing run provides the integration build signal required before review.

## A-F PR Review Rubric

| Grade | Code quality | Test quality | Required action |
| --- | --- | --- | --- |
| A | Clear, focused, maintainable, follows architecture and privacy rules. | Relevant unit/integration tests cover the change and meaningful edge cases. | Ready for human review. |
| B | Sound implementation with minor non-blocking improvement opportunities. | Tests cover the primary behavior; small edge-case gap is documented. | Ready for human review with notes. |
| C | Works, but design, readability, scope control, or documentation needs meaningful follow-up. | Important edge cases or integration coverage are missing. | Fix before requesting merge unless a human accepts the risk. |
| D | Material maintainability, correctness, security, or scope problem. | Insufficient to establish confidence. | Block and rework. |
| E | Serious defect or unsafe design likely to harm the POC or evidence integrity. | Missing or misleading tests. | Reject and redesign. |
| F | Broken, unsafe, non-compliant, or unrelated to the story. | No credible verification. | Do not review or merge. |

For every PR, record separate `Code quality` and `Testing quality` grades. Coding agents may self-review to identify problems, but they may not self-approve or merge.

## Required Repository Settings

An organization owner or repository administrator must configure these GitHub settings; no source file can grant or remove merge authority:

- Make `development` the default branch.
- Protect `development` and `main` against direct pushes.
- Require a pull request before merging.
- Require the `Quality gates` status check to pass.
- Require at least one human approval where the organization policy permits.
- Disable auto-merge for coding-agent accounts and do not grant them maintain or admin roles.
