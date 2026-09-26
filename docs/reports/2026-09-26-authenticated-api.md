# Authenticated backend completion report

## Completed

Implemented the agreed pre-frontend API batch: local administrator bootstrap; reviewer login; viewer/editor/reviewer/admin roles; account controls; expiring/revocable sessions; ingestion, revision, submission, approval/rejection, retirement, outcome application, review queue/packets, retrieval, skills and evaluation endpoints. Authentication does not bypass existing evidence and review gates.

Object revisions and authenticated account/session/request context are transactional. Legacy CLI history stays explicitly unauthenticated. Additive migration preserves prior records. Backups preserve accounts, sessions and audit context. Passwords use salted PBKDF2; only token hashes are stored. Added request limits, strict JSON validation, throttling, conflict responses and secret-safe error handling.

Added [operator/API documentation](../API.md), [architecture decision](../architecture/ADR-004-authenticated-api.md), pinned installed dependencies and package version 0.2.0. No frontend changes.

## Verified

- `.venv/Scripts/python.exe -m unittest discover -v`: **101 tests passed in 72.450 seconds** (31 new auth/API tests plus all 70 prior tests).
- Coverage includes role denials, account lifecycle, expiry/revocation, password controls, actor spoofing, authenticated history, rollback on failed audit insertion, stale writes, simulated full learning cycle, read-only evaluations, migrations and backup restoration.
- `.venv/Scripts/python.exe -m pip check`: no broken requirements.
- CLI validation: nine schemas and 13 fictional records pass.
- Actual CLI/Uvicorn loopback smoke test on temporary database: `/health` returned 200; unauthenticated `/v1/status` returned 401. Smoke server was stopped afterward.
- Existing live pilot: ten drafts, zero eligible records. No real approvals or fabricated reviewer accounts were created.

An initial regression invocation used system Python, which lacks project dependencies and failed imports. The complete successful run used the documented project virtual environment. HTTP tests use HTTPX ASGI transport; the separate smoke test checks actual socket serving.

## Achieved

The backend can now be operated through authenticated HTTP without a frontend. Roles control who can change knowledge and who can approve it, while history attributes API changes to the signed-in account. This proves implemented behavior under the covered tests, not proven real-world design quality or production security certification.

## Remaining outside completed implementation

1. Operator chooses a private administrator password and provisions real reviewers using the documented commands/API.
2. Humans evaluate the W3C pilot, record actual decisions, then test retrieval against approved knowledge.
3. A real design project supplies artifacts and measured outcomes. Fixture simulations cannot substitute for these.
4. Public deployment and external Studio/Figma/model integrations require concrete targets and their own operational/security work. No public server is left running.

Frontend remains deferred as requested. No further coding items remain in the agreed authenticated-API batch.
