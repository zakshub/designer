# Real-source pilot and reviewer tooling report

Date: 2026-09-25. Result: implementation verified; live source review remains pending.

## Completed

- Prepared ten attributed, non-fictional draft records from three official W3C pages: three sources, four evidence records, two contextual claims and one audit skill.
- Separated the pinned normative Recommendation from informative explanations. All sources share one origin group; the claims remain provisional.
- Added review-queue and review-packet commands with source-first ordering, complete upstream records, exact revisions, history and publication blockers.
- Reused the same approval checks for both actual review and explanatory packets, including historical project-learning revision checks.
- Added a strict eight-case retrieval suite and a read-only evaluation runner using a consistent SQLite read snapshot.
- Ingested the pilot into ignored local data/wcag-labels-pilot.sqlite3. All ten records are drafts with review=null; zero records are active guidance.

## Verified

- **70 tests passed**, 0 failures, in 35.383 seconds on Python 3.13 / Windows. This includes the previous 51 tests and 19 new pilot/review/evaluation tests.
- All ten pilot records passed existing schema and graph validation.
- The eight proposed retrieval expectations passed on explicitly simulated, approved fixture copies in temporary databases.
- The actual live intake correctly reports **blocked**: five positive queries await review and three empty-result checks pass. CLI exit code 2 was verified.
- Review packets, queues and evaluations preserve objects, confidence and audit history.
- Invalid suites, duplicate case IDs, unknown targets, contradictory expectations, invalid limits and stale/expired dependencies were checked.
- Wrong and forbidden retrieval results produce failure rather than success.
- Same-origin W3C documents cannot be promoted to canonical trust as independent corroboration.
- Git whitespace validation passed.

## Achieved

Sentinel can now move from a synthetic demonstration to a concrete, reviewable source intake. An operator can see what blocks publication, inspect the exact evidence chain, and evaluate retrieval separately from human approval or design outcomes.

## Remaining

A human must inspect attribution, intended-use rights, applicability and interpretation, then review sources before evidence, claims and skills. No source rights clearance or human approval has been fabricated. A real project artifact and observed outcomes are still needed before claiming a completed real-world learning cycle.

The proposed query expectations cover a tiny corpus and are not an empirical assessment of design quality. Hosted API/authentication and actual external tool integrations remain later backend work. Frontend is not started.

## Artifacts

- [Pilot guide and official sources](../../pilots/wcag-labels/README.md)
- [Actual unapproved intake](../../pilots/wcag-labels/intake/knowledge_web-visible-label-name.json)
- [Retrieval suite](../../pilots/wcag-labels/retrieval-suite.json)
- [Captured live baseline report](../../pilots/wcag-labels/baseline-evaluation.json)
- [Architecture decision](../architecture/ADR-003-real-source-pilot.md)
- [Operator commands](../RUNBOOK.md)

The baseline report is an as-of snapshot. Re-run evaluate after any reviews or revisions; never edit this baseline to imply later approvals.
