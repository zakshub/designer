# Executable architecture

JSON contracts → policy engine → SQLite memory → CLI. Schema resources resolve offline.

| Concept | Current implementation |
| --- | --- |
| Cortex | Human context and synthesis supported by contextual retrieval |
| Memory | Objects, revision snapshots, outcome application ledger |
| Senses | Manual attributed draft ingestion |
| Nervous system | Typed graph links and dependency invalidation |
| Taste | Context, limitations and quality policies; human judgment |
| Critic | Critique, experiments, counterevidence and conflicts |
| Immune system | Schema, graph, rights, trust, review and fixture checks |
| Experiment lab | Hypothesis, method, criteria and result records |
| Evolution engine | Reviewed confidence changes, expiry and retention |
| Hands | CLI and validated Designer/Studio messages; external tool adapters remain future work |

sentinel/model.py owns contracts/policy. sentinel/store.py owns transactions/history/backups. sentinel/engine.py owns reviewed operations, retrieval and skill access. sentinel/studio.py validates role-separated acceptance. sentinel/__main__.py exposes commands.

Each mutation records actor, reason, time and resulting revision. Upstream content changes mark published dependents stale transitively; republishing the source does not silently restore dependent approvals.

Discovery/extraction are recorded as manual drafts. Reviewed evidence supports contextual claims. Project learning records a used revision, artifact, critique and outcome evidence. Applying it proposes a confidence change that requires further review.

Fixture and live modes use separate databases. No autonomous reasoning, source fetching, tool execution, hosted API or scheduler is claimed.
