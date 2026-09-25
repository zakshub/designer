# Typed relationships

| Field | From | To |
| --- | --- | --- |
| source_id | evidence / reference | source |
| source_ids | expert-profile | source |
| evidence_ids | knowledge / conflict / project-learning | evidence |
| counterevidence_ids | knowledge | evidence |
| result.evidence_ids | experiment | evidence |
| knowledge_ids | skill | knowledge |
| knowledge_id | experiment / project-learning | knowledge |
| claim_ids | conflict | two or more distinct knowledge objects |
| successor_id | superseded object | same type |

Targets must exist and share fixture/live mode. Stable IDs refer to current objects; history preserves revisions. Project learning pins the exact published knowledge revision used.

Changing an upstream object invalidates published dependents transitively. Re-review is required before reuse. Relationships describe provenance and usage, not proof of causality. Independent groups represent original origins, not multiple URLs repeating one source.
