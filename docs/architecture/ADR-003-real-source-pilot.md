# ADR-003: Real-source intake and review-aware evaluation

Date: 2026-09-25. Status: accepted for the next local backend batch.

## Scope

Prepare a bounded, real-source pilot on web form labels and accessible names, using the pinned WCAG 2.2 Recommendation and two official WAI explanations inspected on this date. Keep all records as unapproved live drafts. Do not substitute an automated test or an AI summary for a human review.

## Decisions

- Store original concise paraphrases, precise source URLs/sections, dates, provenance, scope and limitations; no copied page archive or autonomous crawler.
- Treat W3C standard and WAI explanations as one origin group. Explanations are informative, not additional normative requirements or independent empirical confirmation.
- Rights metadata awaits reviewer confirmation. Draft intake is permitted; publishing requires the existing explicit rights and review gates.
- Add read-only review-queue and review-packet operations. They expose dependency blockers and exact revisions, and use the same publication checks as approval.
- Add a strict, versioned retrieval evaluation suite with explicit expected and forbidden IDs. Pending positive-case evidence yields blocked, not a false success or a relevance failure. Negative cases may pass while the overall suite remains blocked.
- Evaluations never grant approvals, modify confidence or record a project outcome. Proposed relevance expectations are software-test judgments, not measured user results.
- Preserve the fixture/live boundary. Tests that simulate approvals use fixture-mode copies in temporary databases; the checked-in pilot and persistent live intake remain drafts.

## Changes and verification

Add pilots/wcag-labels/, sentinel/review.py, sentinel/evaluation.py, CLI commands, tests and operator instructions. Reuse the existing object schemas and lifecycle; no database migration is required. Verify dependency ordering, stale/expired records, consistent review gates, read-only behavior, malformed evaluation suites, expected retrieval, blocked-state exit codes and unchanged live approvals.
