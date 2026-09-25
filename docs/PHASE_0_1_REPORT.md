# Phase 0/1 and local backend completion report

Date: 2026-09-25. Scope: the three supplied handoff documents plus the user's authorization to complete backend work before frontend.

This is the historical Phase 0/1 checkpoint. For the subsequent real-source intake and current test totals, see the [pilot batch report](reports/2026-09-25-real-source-pilot.md).

## Outcome

Sentinel now has enforceable contracts and a working local supervised learning cycle. The implementation records attributed knowledge, retrieves it by context, preserves contradictions, learns from reviewed outcomes, and removes outdated guidance while retaining history. Actual synthesis, source evaluation, artifact production and design critique remain human/external activities.

## Architecture and repository

```text
README.md / SENTINEL.md         entry point, identity and mission
requirements.txt / .lock       dependency bounds and verified versions
constitution/                  governing evidence, originality, review and role policies
brain/                         architecture, taxonomy, relationships, ingestion and retrieval
schemas/                       common metadata and nine strict object schemas
examples/                      13 fictional drafts spanning all nine types
sentinel/model.py              offline schema validation and graph/publication policies
sentinel/store.py              SQLite transactions, current objects, history, backups
sentinel/engine.py             review, retrieval, outcome and retention operations
sentinel/studio.py             Designer/Studio message and separate QC contract
sentinel/__main__.py           CLI and synthetic complete-cycle demonstration
tests/                         contract, failure, workflow, persistence and QC tests
validation/                    PowerShell verification entry point
docs/architecture/             ADR-001 and ADR-002
docs/RUNBOOK.md                 commands, review workflow and recovery
docs/STATUS.md                  progress and outstanding integration work
docs/00_*, 12_*, 15_*           original handoff, preserved
```

## Handoff acceptance answers

| Question | Answer and implementation |
| --- | --- |
| What is Sentinel? | Persistent design judgment support, governed by SENTINEL.md and constitution. |
| What does indefinite mean? | Repeated correction, retention and learning over time, not infinite knowledge. |
| How does knowledge enter? | Manual attributed source/evidence drafts through ingest, validated before storage. |
| How does it become trusted? | Dependency-first human review, rights checks, confidence rationale and independent-source gates. |
| How are contradictions represented? | Conflict objects and counterevidence; retrieval exposes dissent and context. |
| How is staleness handled? | Mandatory review dates, query-time expiry and transitive stale propagation. |
| How does it forget? | Retirement/supersession exclude active use while preserving audit history. |
| How do skills use knowledge? | Explicit knowledge IDs, current-dependency checks, evidence-bearing instruction retrieval. |
| How do Designer and Studio cooperate? | Brief/delivery contract; separate image-QC and design-fit passes are both required. |
| What prevents generic design? | Required context, evidence, limitations and critique plus human originality/quality review; software alone cannot guarantee taste. |
| How does learning affect later decisions? | Reviewed outcomes propose confidence/evidence revisions; updated claims require approval before retrieval. |

## Verification evidence

- Python 3.13 on Windows: **51 tests passed**, 0 failed, in 7.321 seconds.
- All **13 fictional objects across 9 object types** passed schema and graph validation. The common schema and each object schema passed meta-schema checking.
- PowerShell validation wrapper and CLI help: passed.
- Full CLI demonstration: passed. The claim appears before update, disappears during renewed review, reappears after approval, and disappears after retirement. Synthetic confidence changes from 0.55 to 0.65.
- Backup recovery preserves current records, history and the applied-outcome ledger. Overwriting an existing backup is refused. Independent database connections reject stale editor revisions.
- Dependency installation consistency: `pip check` passed; exact installed versions are recorded in requirements.lock.

Verification found and fixed permissive calendar-date checking and a Windows-only temporary-database cleanup-order failure. The final run above includes those fixes. The local Git ownership issue caused by sandbox initialization was repaired by preserving the empty original metadata under ignored data/sandbox-git-initialization and initializing under the host account. No source files or history were deleted.

## Known limits

- All supplied knowledge at this checkpoint was synthetic. The later pilot adds unapproved source-grounded drafts; there is still no real approved design corpus or empirical evidence of improved design quality.
- Reviewer identity and source-origin independence are operator assertions, not authenticated or automatically proven facts.
- Rights and substantive originality require review; text fields cannot establish them.
- Lexical retrieval uses exact domain/platform and token overlap; it is not semantic intelligence and needs evaluation on a real corpus.
- Full-graph validation is appropriate for a small local corpus; larger collections need measured indexing/caching work.
- SQLite and the CLI are local tools. No hosted service, external model execution or autonomous source collection is included.
- Confidence thresholds and maximum delta are policy defaults, not statistically calibrated probabilities.
- Backups preserve history; exports of current objects do not. No hard-delete/privacy-erasure workflow is supplied.

## Recommended next work

Run a real human-reviewed design pilot using the runbook. Measure contextual retrieval, contradiction handling and correction quality, then refine the policies. Define the actual Studio/tool integration and hosting requirements before adding adapters or a multi-user API. Frontend remains a later consumer of meaningful backend state.
