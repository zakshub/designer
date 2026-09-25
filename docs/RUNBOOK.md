# Operator runbook

Run commands from the repository root using `.venv/Scripts/python.exe`. The Windows setup and install commands are in README.md. Installation needs package access once; normal operation resolves schemas locally and needs no network.

## Validate and demonstrate

```powershell
.\.venv\Scripts\python.exe -m sentinel validate
.\.venv\Scripts\python.exe -m unittest discover -v
.\.venv\Scripts\python.exe -m sentinel --db :memory: --fixture-mode demo
```

All checked-in examples are fictional drafts. The demo simulates review and prints the before/after retrieval results, the confidence change from 0.55 to 0.65, and immutable history snapshots. Its database must be empty. An in-memory demo leaves no persistent research records.

## Live workflow

Use a separate database without `--fixture-mode`. Author JSON records with actual attribution, dates, rights, context and `fixture: false`; do not relabel the examples as real observations. Each new record starts at revision 1, lifecycle draft, review null. Put each object in its own JSON file in an intake directory.

```powershell
.\.venv\Scripts\python.exe -m sentinel --db data/live.sqlite3 ingest intake --actor operator --reason "Capture source and observation for review"
.\.venv\Scripts\python.exe -m sentinel --db data/live.sqlite3 status
.\.venv\Scripts\python.exe -m sentinel --db data/live.sqlite3 show source_your-source
.\.venv\Scripts\python.exe -m sentinel --db data/live.sqlite3 submit source_your-source --expected 1 --actor operator --reason "Ready for source review"
.\.venv\Scripts\python.exe -m sentinel --db data/live.sqlite3 review source_your-source --expected 2 --actor actual-reviewer --reason "Attribution, rights and scope checked" --decision approve
```

The names and IDs above are placeholders, not records already present. The reviewer supplies their own substantive findings. Review sources first, then evidence, claims, and their consumers. `show` returns the current revision for `--expected`; stale editor revisions fail rather than overwrite another change. Use `--decision reject` to return work to draft with a reason.

## Use and learn

```powershell
.\.venv\Scripts\python.exe -m sentinel --db data/live.sqlite3 retrieve "action labels" --domain ui --platform mobile
.\.venv\Scripts\python.exe -m sentinel --db data/live.sqlite3 use-skill skill_your-skill
```

Inspect context, limitations, conflicts, confidence rationale and evidence before deciding. A skill returns instructions and supporting records; it does not execute an external design tool.

Record the actual produced artifact locator, critique and observed outcome in a project-learning object. Pin the published knowledge revision used. Capture and review the outcome's evidence/source first, then submit/review the project-learning object. A planned experiment can remain a draft; it cannot publish a result until completed with evidence.

`apply-outcome ID --expected KNOWLEDGE_REVISION --actor NAME --reason TEXT` applies a reviewed outcome once. It proposes a bounded confidence adjustment, attaches evidence and returns the claim to in-review. Approve or reject that new revision explicitly. If the recorded knowledge revision is no longer current, reassess applicability and revise the outcome first.

## Correct and retain

`revise ID changes.json --expected N --actor NAME --reason TEXT` accepts a JSON object of changed content fields. The engine clears approval and marks published dependents stale. Identity, fixture mode, review metadata and lifecycle cannot be injected through this patch.

`sweep --actor NAME --reason TEXT` marks overdue published records stale and propagates invalidation. Retrieval enforces expiry even without a sweep. This is a manual operation, not a scheduled automation.

`retire ID --expected N --actor NAME --reason TEXT` withdraws guidance. Add `--successor SAME_TYPE_ID` for supersession. A successor must already be current and approved. Superseded records remain immutable. Retired/stale records can be revised and reviewed again. A source's renewed approval does not automatically reactivate stale dependents.

`history ID` returns revision snapshots with actor, reason, action and timestamp. Historical conflicts remain visible as non-current dissent where applicable.

## Backup and recovery

```powershell
.\.venv\Scripts\python.exe -m sentinel --db data/live.sqlite3 backup data/backups/brain-001.sqlite3
.\.venv\Scripts\python.exe -m sentinel --db data/backups/brain-001.sqlite3 status
```

Backups include records, review history, applied-outcome ledger and database mode. Existing destination paths are refused. Recover by selecting the snapshot with `--db`, keeping the original untouched. Fixture backups still require `--fixture-mode`.

`export` emits current objects as JSON for inspection, but omits revision history and is not a recovery format. Imports deliberately reject preapproved snapshots; use database backups for recovery.

## Operating boundary

This is a trusted local operator tool. Reviewer identity, source independence, rights, expert authority, critique and actual design fit require honest human evaluation. Local file owners can alter SQLite directly; audit history is not a cryptographic tamper-proof log. Authentication and network transport are required before exposing it to untrusted users.
