# ADR-001: Phase 0–1 governed knowledge foundation

**Status:** accepted (initial implementation)  
**Date:** 2026-09-25

## Context

Sentinel needs to learn design judgment over time without becoming an unstructured archive, generic assistant, or unreviewed crawler.

## Decision

Use versioned JSON Schema objects with stable, typed identifiers. Separate sources (where material came from), evidence (what was observed), knowledge (a contextual claim), and outcomes (what happened when the claim was used). Make reviewer state, confidence, rights, staleness, conflicts, and retirement explicit. Keep data fixtures fictional and reviewed.

## Consequences

The repository gains a durable, tool-agnostic contract before automation. Ingestion and retrieval will be slower initially because they require metadata and review, but outputs can be audited and corrected. Phase 2 may add a reviewed ingestion service and retrieval layer; it must preserve these contracts.

## Planned file changes

Added: constitution policies, `SENTINEL.md`, `brain/`, `schemas/`, `validation/`, and `examples/`. No existing repository file was moved or replaced because the working directory contained only the supplied handoff documents.
