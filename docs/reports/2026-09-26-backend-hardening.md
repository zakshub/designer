# Backend hardening and CI report

## Completed

- Closed the authentication-to-write revocation race: authenticated writes revalidate the session inside the SQLite write transaction. A revocation committed first prevents the write and rolls it back.
- Rejected JSON numeric overflow (`1e999`) and escaped unpaired Unicode surrogates, including keys, before endpoint processing.
- Added regressions for mid-request revocation, two concurrent edits with the same expected revision (one success, one conflict), and malformed JSON.
- Added GitHub Actions CI for Windows/Linux with Python 3.11/3.13: locked install, dependency check, schema validation, complete tests and synthetic learning demo. Read-only permissions, no persisted checkout credentials, no secrets/deployment, 15-minute timeout, and upstream-verified immutable action commits.
- Documented transaction ordering and CI boundaries in [ADR-005](../architecture/ADR-005-backend-hardening.md) and API documentation. Host-workspace-operator guidance kept edits scoped and the existing pilot untouched.

## Verification

- Project virtual environment, Windows/Python 3.13: **104 tests passed in 65.630 seconds**; the focused auth/API run passed all 34 tests.
- Dependency check: no broken requirements.
- Schema validation: all nine schemas and 13 fixture objects pass.
- In-memory synthetic learning demo: exit 0, including confidence update and retirement behavior.
- Live pilot: ten drafts, zero eligible records. No real review or account changes.
- CI action hashes resolved directly from public upstream repositories. GitHub workflow execution is not yet verified; nothing was pushed.

## Achieved and remaining

The backend now handles the covered revocation race, concurrent-edit conflict and malformed-input cases, and repeatable CI checks are ready for remote execution. This is targeted hardening, not a comprehensive security audit.

Remaining: execute CI on GitHub after an authorized push (including Linux/Python 3.11 verification); choose real administrator credentials; conduct human pilot review and actual project evaluation. Public deployment and external integration targets remain undefined. Frontend remains deferred.
