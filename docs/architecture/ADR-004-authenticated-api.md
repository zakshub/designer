# ADR-004: Authenticated local backend API

Date: 2026-09-26. Status: accepted.

## Authorized scope

Implement the agreed backend plan: reviewer login and roles; ingestion, review, retrieval and evaluation endpoints; authenticated identities in audit history; tests and operator documentation. The existing live pilot remains unapproved until an actual reviewer decides. Frontend and public deployment are not part of this batch.

## Design

- FastAPI provides validated JSON requests and OpenAPI; Uvicorn serves on loopback by default. Core knowledge schemas and the Brain workflow remain authoritative.
- Viewer can read; editor can ingest/revise/submit; reviewer can also approve/reject, apply outcomes and retire; admin additionally manages users. Usernames are immutable. All roles operate within one local corpus, not separate tenants.
- A local interactive bootstrap command creates the first administrator with a password chosen by the operator. No default password, automatic reviewer account or embedded secret.
- Password hashes use PBKDF2-HMAC-SHA256 with 600,000 iterations, random salts and constant-time comparison. Opaque session tokens are random, expire, can be revoked, and are stored only as hashes. Login failures are throttled per account and client address.
- Roles and active status are checked from the database for every authenticated request. Role/password changes and deactivation revoke existing sessions. The last active administrator cannot be disabled or demoted through the API.
- API callers cannot supply the acting reviewer. History stores the authenticated principal, role, session ID and server-generated request ID in the same transaction as each object revision. Existing CLI history remains explicitly unattested by API authentication.
- Additive auth/audit migration preserves existing object IDs, revisions, fixtures and review state. Backups include the new tables. Schema incompatibility fails closed.
- Limit request bodies, reject unknown payload fields, and return stable status/error envelopes without echoing passwords or tokens. No browser CORS origins are enabled by default. Credentials are JSON POST bodies, never URL parameters.
- Network TLS and reverse-proxy rate limiting are deployment responsibilities; the supplied serve command binds only to loopback. This is an authenticated local service, not an internet deployment or a claim of production security certification.

## Verification

Test login, wrong credentials, lockout, expiry/revocation, role enforcement, spoofed identities, history attribution, validation errors, stale revisions, complete reviewed API lifecycle, evaluations, migrations and backup recovery. Keep all automated approvals in fixture databases. Run the existing regression suite and confirm the live pilot still has no approvals.

## References

- https://fastapi.tiangolo.com/reference/security/
- https://fastapi.tiangolo.com/tutorial/testing/
- https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
