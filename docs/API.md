# Authenticated local API

The backend exposes the existing review and learning rules over HTTP. Frontend is not required. Use Python from the repository virtual environment.

## Start

```powershell
.\.venv\Scripts\python.exe -m sentinel --db data/live.sqlite3 bootstrap-admin operator
.\.venv\Scripts\python.exe -m sentinel --db data/live.sqlite3 serve --port 8000
```

Choose a unique 15–128 character password at the hidden prompts. Bootstrap works only when no accounts exist. No default credentials are shipped. To use the existing pilot, substitute `data/wcag-labels-pilot.sqlite3` in both commands; bootstrap does not approve its drafts. Do not send passwords in chat or commit credentials.

Server binds to `127.0.0.1`; `GET /health` is public. POST `/v1/auth/login` with JSON `username` and `password` returns `data.access_token`. Keep it in memory and send `Authorization: Bearer TOKEN`. Tokens expire after one hour; logout revokes the current token. Password or role changes and deactivation revoke all sessions for that account. Failed logins are throttled. Never put credentials in URLs.

## Permissions and routes

Roles inherit all lower-role permissions within a single corpus (not separate tenants).

| Minimum role | Operations |
| --- | --- |
| Viewer | GET `/v1/status`, `/v1/objects`, `/v1/objects/{id}`, `/v1/objects/{id}/history`, `/v1/objects/{id}/review-packet`, `/v1/review-queue`, `/v1/retrieve`, `/v1/skills/{id}/use`, `/v1/openapi.json`; POST `/v1/evaluate` |
| Editor | POST `/v1/objects`, PATCH `/v1/objects/{id}`, POST `/v1/objects/{id}/submit` |
| Reviewer | POST `/v1/objects/{id}/review`, `/retire`, `/apply-outcome`; POST `/v1/maintenance/sweep` |
| Admin | GET/POST `/v1/users`, PATCH `/v1/users/{id}`, POST `/v1/users/{id}/password`, GET `/v1/audit/security` |

Every authenticated role can GET `/v1/auth/me`, POST `/v1/auth/logout`, and POST `/v1/auth/password`. The last active administrator cannot be demoted or disabled. Account administration requires a reason. The authenticated OpenAPI document contains exact parameters and payload schemas.

## Payloads and responses

- Ingestion: `{"objects": [OBJECT], "reason": "Source intake"}`; up to 100 draft objects per request. Server assigns `created_by` from the authenticated account; source authorship remains source data.
- Revision: `{"expected": 1, "changes": {"title": "Corrected title"}, "reason": "Correction"}`.
- Submit: `{"expected": 1, "reason": "Ready for review"}`.
- Review: `{"expected": 2, "decision": "approve", "reason": "Actual reviewer findings"}`; decision can also be `reject`.
- Retirement adds optional `successor_id`; outcome application uses the target knowledge's expected revision. Sweep needs `reason` only.
- Evaluation: `{"suite": SUITE}`. HTTP 200 means evaluation ran; inspect `data.status` for pass, fail or blocked. Evaluation never approves records.
- Create user: `{"username": "reviewer.name", "password": "CHOOSE_A_UNIQUE_SECRET", "role": "reviewer", "reason": "Reviewer provisioning"}`. This is a shape example, not a usable default credential.
- Password change uses `current_password` and `new_password`; administrator reset uses `new_password` and `reason`.

JSON successes contain `data` and `request_id` (OpenAPI returns the schema directly). Errors contain `error.code`, `error.message`, optional sanitized details, and `request_id`. Common statuses: 401 authentication, 403 permissions, 404 missing record, 409 revision/duplicate conflict, 413 body over 1 MiB, 415 content type, 422 invalid input/domain transition, 429 throttled, 503 storage failure. Unknown fields, duplicate JSON keys and non-finite numbers are rejected. Object and security-event listings are paginated with a maximum limit of 100.

## Audit, backups and boundaries

Object changes and their authenticated context commit atomically: account ID, username, role, session ID and server request ID. Clients cannot supply an actor. Login, account changes and permission denials have a separate security-event log. Passwords and raw tokens are not stored in these logs.

Existing records migrate additively. Older/CLI history explicitly reports `authenticated: false` and `via: local-cli`; the CLI is still a trusted filesystem-owner interface, not an authentication boundary. SQLite owners can modify the database directly; history is not tamper-proof.

Use the runbook's SQLite backup command. Backups contain password hashes and active session hashes as well as records/history: protect them as sensitive files. Restored unexpired sessions remain valid, so choose recovery files carefully and revoke sessions through account controls where needed. JSON export is not a backup.

No CORS origins are enabled. Only localhost hostnames are accepted. Public hosting still needs a defined deployment target, TLS, proxy/rate-limit configuration, operating-system access controls and an independent security review. This release does not supply internet deployment or automated human approvals.
