# Real-source pilot: web labels

This pilot contains ten source-grounded, unapproved records: three sources, four evidence records, two contextual knowledge claims and one review skill. Original summaries were prepared from the sources below on 2026-09-25. No real user study, product audit, human approval or accessibility conformance result is claimed.

## Sources and scope

- [WCAG 2.2, Recommendation of 12 December 2024](https://www.w3.org/TR/2024/REC-WCAG22-20241212/), specifically [2.5.3](https://www.w3.org/TR/2024/REC-WCAG22-20241212/#label-in-name) and [3.3.2](https://www.w3.org/TR/2024/REC-WCAG22-20241212/#labels-or-instructions). This is a pinned normative version, not a claim that no newer version exists.
- [WAI: Understanding Label in Name](https://www.w3.org/WAI/WCAG22/Understanding/label-in-name.html), informative explanation of the visible-label/programmatic-name relationship.
- [WAI: Understanding Labels or Instructions](https://www.w3.org/WAI/WCAG22/Understanding/labels-or-instructions.html), informative explanation of input guidance and the distinction from programmatic naming.

All three sources belong to the same `w3c-wcag` independence group. Extra explanatory pages do not count as independent corroboration. The two knowledge claims remain provisional. Their proposed confidence refers to our contextual interpretation, not whether a normative requirement is optional.

Records store links and concise original paraphrases, not page copies. Rights status is unknown pending the reviewer's assessment of intended use and applicable source terms. Evidence keeps observation separate from interpretation. Human reviewers should inspect the precise source locations and boundaries of applicability.

## Start or inspect the pilot

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m sentinel validate pilots/wcag-labels/intake
.\.venv\Scripts\python.exe -m sentinel --db data/wcag-labels-pilot.sqlite3 ingest pilots/wcag-labels/intake --actor codex-source-intake --reason "Source-grounded drafts awaiting human review"
.\.venv\Scripts\python.exe -m sentinel --db data/wcag-labels-pilot.sqlite3 review-queue
.\.venv\Scripts\python.exe -m sentinel --db data/wcag-labels-pilot.sqlite3 review-packet knowledge_web-visible-label-name
.\.venv\Scripts\python.exe -m sentinel --db data/wcag-labels-pilot.sqlite3 evaluate pilots/wcag-labels/retrieval-suite.json
```

Ingestion is a one-time operation. If the pilot database already exists with these IDs, inspect it instead of repeating ingestion. Existing records cannot be overwritten by ingest. The local database is ignored by Git; the draft intake remains reproducible from checked-in files.

The queue lists source work before evidence, claims and skills. Resolve substantive blockers, submit each exact revision, and review it using your own identity and findings. Use the [operator runbook](../../docs/RUNBOOK.md) for revision and review commands. No ready-for-approval flag grants approval automatically.

## Retrieval evaluation

The suite has eight proposed, exhaustive result expectations for this tiny corpus: five positive queries and three scope/unrelated-query checks. It evaluates IDs returned by the current engine, not actual design quality. No judgments have been validated with users or independent assessors.

With only draft records, five cases are blocked awaiting approved knowledge and three empty-result cases pass. The overall status is **blocked**, not a successful live pilot. Positive cases run after their expected records and dependencies are current. A missing expected ID is a suite error; a stored but unapproved ID is a blocked case. A wrong result after approval is a failure.

CLI exit codes: 0 = all checks pass; 1 = failed expectations or invalid input; 2 = pending review blocks evaluation. A failure takes precedence over pending cases. Evaluations operate on a database read snapshot and never publish, change confidence or record outcomes.

Automated tests simulate approval only on fixture-mode copies in temporary databases. Those simulations can validate the eight retrieval expectations without writing human approvals into this live intake.

## Human pilot still to perform

Review the ten records, then apply the approved claims to an actual web form/control set. Record the real artifact, observed accessibility properties, critique, limitations and the knowledge revisions used. Only actual observations may support a project-learning record and confidence change. Neither the source summaries nor passing software tests substitute for that work.
