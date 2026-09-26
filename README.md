# Sentinel Designer Brain

Sentinel is a local backend for developing design judgment through attributed evidence, human review, contextual retrieval, experiments, outcomes, correction, and retention.

Phase 0/1 contracts and a supervised backend learning cycle are implemented. Demonstrations use fictional fixtures; they do not claim real research, actual human approval, or proven improvements to design quality.

## Run on Windows

From the repository root, using Python 3.11 or newer:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m sentinel validate
.\.venv\Scripts\python.exe -m unittest discover -v
.\.venv\Scripts\python.exe -m sentinel --db :memory: --fixture-mode demo
```

The demo needs no network or credentials. A persistent demo can use a new path such as `--db data/demo.sqlite3`; it refuses a populated database. Live databases reject fixture records.

## Implemented

Nine strict object schemas; typed references; manual ingestion and review; contextual retrieval with provenance; conflicts and counterevidence; reviewed confidence updates; SQLite persistence and revision history; concurrency checks and backups; expiry, supersession and retirement; Designer/Studio handoff validation.

The [real-source web-label pilot](pilots/wcag-labels/README.md) adds ten unapproved W3C-grounded records, dependency-ordered review packets and eight proposed retrieval checks. `review-queue`, `review-packet` and `evaluate` are read-only operations; pending review remains visibly blocked.

## Navigation

- [Identity](SENTINEL.md) and [constitution](constitution/README.md)
- [Architecture](brain/architecture.md), [schemas](schemas/README.md), [validation](validation/README.md)
- [Operator runbook](docs/RUNBOOK.md)
- [Authenticated API and account setup](docs/API.md)
- [Completion report](docs/PHASE_0_1_REPORT.md) and [status](docs/STATUS.md)
- [Architecture decision](docs/architecture/ADR-002-executable-backend.md)

A future frontend can call the authenticated local HTTP API. Reviewer accounts, role permissions and authenticated audit history are implemented. External model/Studio execution, automated research and public production deployment remain outside this local prototype.

Backend CI is configured for Windows/Linux on Python 3.11 and 3.13 with locked dependencies, schema validation, regression tests and the synthetic learning demo. The workflow uses read-only permissions and pinned action commits; no deployment or real pilot approval is automated. Remote results are available only after the workflow is pushed and runs.
