# Schema contracts v1.0.0

Nine object schemas target JSON Schema draft 2020-12 and share common.schema.json. All references resolve locally. Unknown fields, invalid calendar dates, invalid types, duplicate array references, empty required text and broken graph links fail.

| Type | Meaning |
| --- | --- |
| source | Locator, creator, publisher, independence group, strength, capture date, rights |
| evidence | Observation, separate interpretation, method, locator, scope, limitations |
| knowledge | Contextual claim, supporting/counter evidence, confidence, trust, limitations |
| expert-profile | Attributed expertise, philosophy and explicit limits |
| skill | Inputs, procedure, outputs, quality checks and knowledge dependencies |
| experiment | Hypothesis, method, criteria, planned/completed state and result evidence |
| project-learning | Used knowledge revision, decision, artifact, critique, outcome, lesson, confidence delta |
| conflict | Competing claims, evidence, state and resolution |
| reference | Source, mechanism, use, context and originality note |

Every object has schema_version, id, type, revision, title, created_at, updated_at, created_by, fixture, lifecycle, review, review_due_at and change_reason.

IDs use the exact type plus an underscore and a lowercase slug, including hyphenated types: project-learning_mobile-actions. IDs persist across revisions. Timestamps are UTC RFC 3339 with trailing Z and up to six fractional digits. Imports are new revision-1 drafts; the engine increments revisions.

Review is null until evaluated, or records actor, actor_kind (human/fixture), decision, time and reason. Local reviewer identity is an attestation, not authenticated identity.

The schema checks structure. sentinel/model.py adds graph/trust policy. sentinel/engine.py enforces workflow, historical revision checks, expiry and publication order.

The earlier scaffold was replaced before any live data existed. Future breaking versions require explicit migration; unknown schema versions fail.
