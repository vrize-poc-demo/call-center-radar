#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: npm run pr:verify -- <pr-number>" >&2
  exit 2
fi

pr_number="$1"
base_branch="$(gh pr view "$pr_number" --json baseRefName --jq '.baseRefName')"
head_branch="$(gh pr view "$pr_number" --json headRefName --jq '.headRefName')"
merge_state="$(gh pr view "$pr_number" --json mergeStateStatus --jq '.mergeStateStatus')"
failed_checks="$(gh pr view "$pr_number" --json statusCheckRollup --jq '[.statusCheckRollup[] | select(.status != "COMPLETED" or .conclusion != "SUCCESS")] | length')"
quality_gate_passed="$(gh pr view "$pr_number" --json statusCheckRollup --jq '[.statusCheckRollup[] | select(.name == "Quality gates" and .status == "COMPLETED" and .conclusion == "SUCCESS")] | length')"

if [[ "$base_branch" != "development" ]]; then
  echo "PR #${pr_number} targets '${base_branch}', not 'development'." >&2
  exit 1
fi

if [[ "$head_branch" == "development" || "$head_branch" == "main" ]]; then
  echo "PR #${pr_number} uses a protected branch as its source branch." >&2
  exit 1
fi

if [[ "$merge_state" != "CLEAN" ]]; then
  echo "PR #${pr_number} is not cleanly mergeable: ${merge_state}." >&2
  exit 1
fi

if [[ "$failed_checks" != "0" ]]; then
  echo "PR #${pr_number} has ${failed_checks} incomplete or failed check(s)." >&2
  exit 1
fi

if [[ "$quality_gate_passed" != "1" ]]; then
  echo "PR #${pr_number} does not have a successful Quality gates check." >&2
  exit 1
fi

echo "PR #${pr_number} targets development, is cleanly mergeable, and has passing checks."
