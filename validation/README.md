# Verification

Run `.venv/Scripts/python.exe -m sentinel validate` for full schema and graph validation, or `pwsh -File validation/validate-fixtures.ps1`. Run `.venv/Scripts/python.exe -m unittest discover -v` for behavioral tests.

All nine types have fictional examples. On disk they are unreviewed drafts. Simulated reviews happen explicitly in fixture-only tests and demos.

## Enforced gates

1. Required fields, allowed taxonomy, typed IDs, closed objects, bounded numbers, timestamps and field types.
2. Unique object IDs, existing typed targets, no fixture/live cross-links, no future outcome revisions or supersession cycles.
3. Publication requires review, permitted rights, current approved dependencies and a future review date.
4. Confidence below 0.4 remains a lead. Weak evidence alone cannot publish guidance. Canonical trust and confidence at or above 0.8 need two independent non-weak source groups.
5. Outcomes cite a historically published knowledge revision. Applying an outcome requires that revision still be current.
6. A reviewed outcome changes confidence by at most 0.2, attaches evidence, invalidates dependents and requires renewed claim review.
7. Retrieval excludes expired, stale, retired, superseded, unapproved and transitively invalid records. Previously approved conflicts remain visible as historical dissent.
8. Writes and snapshots commit together. Expected revisions reject stale edits. An outcome ID can be applied once.

Rights, independence, expertise, quality and originality remain human judgments. Validation checks declared metadata; it cannot prove those assertions.
