# ADR-002: Executable backend before frontend

Date: 2026-09-25. Status: accepted for local prototype.

The user has authorized completion of the work preceding frontend. The supplied handoff specifies Phase 0/1 in detail and a human-supervised learning cycle, but no later numbered roadmap. This batch completes those contracts and adds a local working cycle, rather than inventing a production deployment requirement.

## Decisions

- Python 3.11+ with JSON Schema draft 2020-12 validation; SQLite from the standard library for durable transactions and revision history. No remote schema resolution.
- Nine typed, strict object schemas share version, provenance, timestamps, fixture isolation, reviewer attestations, lifecycle, and retention metadata.
- Imported objects must enter as drafts. Publication, content revision, review, confidence updates, staleness, retirement, and supersession are explicit operations. SQLite changes and audit events commit together.
- A human reviewer identity and rationale are supplied by the local operator. This is an attestation, not authenticated identity. A hosted product will need authentication before external users can approve anything.
- Fictional fixtures are clearly marked, use simulated reviewer identities, and are usable only in an explicit fixture-mode database. They never count as real research or completed human review.
- Source diversity, rights, current evidence, and review gates govern publication. Single-source claims can be provisional; canonical claims require at least two independent source groups. Confidence is a reviewed estimate, not a probability of truth.
- Retrieval is deterministic and context-filtered; it exposes conflicts, limitations, evidence, sources, and revision numbers. Querying never raises confidence.
- Outcome application is explicit, reviewed, bounded, and idempotent. Records include the design decision, produced artifact, critique, observation, and lesson. External production tools remain adapters; their execution is not fabricated.
- Staleness excludes evidence transitively at retrieval time. Retirement is reversible through renewed review. Supersession preserves history. Hard deletion is not a learning operation.

## Files

Refactor schemas, fictional examples, validation wrapper, README, and brain documentation. Add `sentinel/`, `tests/`, `requirements.txt`, taxonomy JSON, lifecycle/runbook documents, and an acceptance report. Preserve the original handoff. Local database files and virtual environments are ignored.

## Verification

Validate every schema and fixture, reject malformed and policy-breaking objects, exercise transactional history and failed writes, run the full simulated learning cycle, and verify retrieval before/after review, conflict, expiry, confidence update, and retirement. No frontend is part of this batch.
