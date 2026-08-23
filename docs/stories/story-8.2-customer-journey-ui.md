# Story 8.2: Customer Journey UI

**GitHub issue:** #35

**Status:** In Progress

**Owner:** SusmithaKM

**Epic:** #9 Customer Journey

## 1. Outcome

Renders a narrow chronological customer journey from Story 8.1's persisted history API.

## 2. Design

`/?view=journey&journeyCall=<call-id>` loads the history model and shows mood/outcome, repeated issues, and direct call-detail links. No CRM profile or transcript data is added.

## 3. Operational Behavior

Browser logs load success/failure without customer content. Missing history displays a safe error and a Today link.

## 4. Verification

| Check | Result | Notes |
| --- | --- | --- |
| Web lint | Passed | ESLint passed. |
| Web build | Passed | Vite production build passed. |
| UI test | Pending | Focused timeline test added. |

## 5. Delivery Record

- Branch: `feature/story-8.2-customer-journey-ui`
- Pull request: TBD

### Change Log

| Commit | What changed | Why |
| --- | --- | --- |
| Pending | Added Customer Journey route, timeline, repeated-issue markers, call links, and test. | Implements #35 without expanding into a CRM profile. |
