"""Reviewed state transitions and evidence-bearing retrieval."""

import copy
import re

from .model import Contracts, DOMAINS, Invalid, eligible, instant, links, utcnow
from .review import approval_blockers


class Brain:
    def __init__(self, store, clock=utcnow):
        self.store, self.clock, self.contracts = store, clock, Contracts()

    def _actor(self, actor, reason):
        if not isinstance(actor, str) or not actor.strip() or not isinstance(reason, str) or not reason.strip():
            raise Invalid("Actor and substantive reason are required")

    def _check_revision(self, obj, expected):
        if obj["revision"] != expected:
            raise Invalid(f"Revision conflict: expected {expected}, current {obj['revision']}")

    def _commit(self, obj, action, actor, reason):
        obj["revision"] += 1
        obj["updated_at"] = self.clock()
        obj["change_reason"] = reason
        objects = [o for o in self.store.all() if o["id"] != obj["id"]] + [obj]
        invalidated = []
        if action in ("revise", "apply-outcome", "retired", "superseded", "stale"):
            affected = {obj["id"]}
            # Walk the whole dependency graph, including already inactive intermediates.
            while True:
                newly_affected = {o["id"] for o in objects if o["id"] not in affected
                                  and any(target in affected for target, _ in links(o))}
                if not newly_affected:
                    break
                affected.update(newly_affected)
            for dependent in objects:
                if dependent["id"] != obj["id"] and dependent["id"] in affected and dependent["lifecycle"] == "published":
                    dependent["lifecycle"] = "stale"
                    dependent["revision"] += 1
                    dependent["updated_at"] = obj["updated_at"]
                    dependent["change_reason"] = f"Dependency {obj['id']} changed: {reason}"
                    invalidated.append(dependent)
        self.contracts.graph(objects)
        self.store.save(obj, action, actor)
        for dependent in invalidated:
            self.store.save(dependent, "dependency-stale", actor)
        return obj

    def ingest(self, objects, actor, reason):
        self._actor(actor, reason)
        objects = copy.deepcopy(objects)
        if not objects:
            raise Invalid("An empty ingestion batch is not allowed")
        with self.store.transaction():
            existing = self.store.all()
            existing_ids = {o["id"] for o in existing}
            for obj in objects:
                self.contracts.validate(obj)
                if obj["fixture"] != self.store.fixture_mode:
                    raise Invalid("Fixture/live database mismatch")
                if obj["id"] in existing_ids:
                    raise Invalid(f"ID already exists; revise it explicitly: {obj['id']}")
                if obj["lifecycle"] != "draft" or obj["revision"] != 1 or obj["review"] is not None:
                    raise Invalid("Ingestion accepts only new, unreviewed revision-1 drafts")
                if obj.get("successor_id") or obj.get("retention_reason"):
                    raise Invalid("Draft ingestion cannot impersonate a retention operation")
                if instant(obj["created_at"]) > instant(self.clock()):
                    raise Invalid("Creation timestamp cannot be in the future")
                obj["updated_at"], obj["change_reason"] = self.clock(), reason
            self.contracts.graph(existing + objects)
            for obj in objects:
                self.store.save(obj, "ingest", actor)
        return objects

    def revise(self, object_id, changes, actor, reason, expected):
        self._actor(actor, reason)
        protected = {"id", "type", "schema_version", "revision", "created_at", "updated_at", "created_by",
                     "fixture", "lifecycle", "review", "change_reason", "successor_id", "retention_reason"}
        if not isinstance(changes, dict) or not changes or protected & changes.keys():
            raise Invalid("Supply content changes only; identity, review, and lifecycle are managed by the engine")
        with self.store.transaction():
            obj = self.store.get(object_id)
            self._check_revision(obj, expected)
            if obj["lifecycle"] == "superseded":
                raise Invalid("Superseded objects are immutable; revise the successor")
            obj.update(copy.deepcopy(changes))
            obj["lifecycle"], obj["review"] = "draft", None
            obj.pop("retention_reason", None)
            return self._commit(obj, "revise", actor, reason)

    def submit(self, object_id, actor, reason, expected):
        self._actor(actor, reason)
        with self.store.transaction():
            obj = self.store.get(object_id)
            self._check_revision(obj, expected)
            if obj["lifecycle"] != "draft":
                raise Invalid("Only drafts can be submitted")
            obj["lifecycle"], obj["review"] = "in-review", None
            return self._commit(obj, "submit", actor, reason)

    def review(self, object_id, actor, reason, expected, approve=True):
        self._actor(actor, reason)
        with self.store.transaction():
            obj = self.store.get(object_id)
            self._check_revision(obj, expected)
            if obj["lifecycle"] != "in-review":
                raise Invalid("Only submitted objects can be reviewed")
            if approve:
                index = {o["id"]: o for o in self.store.all()}
                reasons = approval_blockers(self, obj, index, self.clock())
                if reasons:
                    raise Invalid("; ".join(reasons))
            obj["lifecycle"] = "published" if approve else "draft"
            obj["review"] = {"actor": actor, "actor_kind": "fixture" if self.store.fixture_mode else "human",
                             "decision": "approved" if approve else "rejected", "at": self.clock(), "reason": reason}
            return self._commit(obj, "approve" if approve else "reject", actor, reason)

    def retire(self, object_id, actor, reason, expected, successor_id=None):
        self._actor(actor, reason)
        with self.store.transaction():
            obj = self.store.get(object_id)
            self._check_revision(obj, expected)
            if obj["lifecycle"] in ("retired", "superseded"):
                raise Invalid("Object is already inactive")
            if successor_id:
                index = {o["id"]: o for o in self.store.all()}
                successor = index.get(successor_id)
                if successor_id == object_id or not successor or successor["type"] != obj["type"] or not eligible(successor_id, index, self.clock()):
                    raise Invalid("Successor must be a distinct current approved object of the same type")
                obj["successor_id"] = successor_id
            obj["lifecycle"] = "superseded" if successor_id else "retired"
            obj["retention_reason"] = reason
            return self._commit(obj, obj["lifecycle"], actor, reason)

    def sweep(self, actor, reason):
        self._actor(actor, reason)
        changed = []
        with self.store.transaction():
            for snapshot in self.store.all():
                obj = self.store.get(snapshot["id"])
                if obj["lifecycle"] == "published" and instant(obj["review_due_at"]) <= instant(self.clock()):
                    obj["lifecycle"] = "stale"
                    changed.append(self._commit(obj, "stale", actor, reason))
        return changed

    def apply_outcome(self, outcome_id, actor, reason, expected):
        self._actor(actor, reason)
        with self.store.transaction():
            outcome = self.store.get(outcome_id)
            if outcome["type"] != "project-learning":
                raise Invalid("Only project-learning records can update confidence")
            if self.store.db.execute("SELECT 1 FROM applied_outcomes WHERE outcome_id=?", (outcome_id,)).fetchone():
                raise Invalid("This outcome has already been applied")
            index = {o["id"]: o for o in self.store.all()}
            if not eligible(outcome_id, index, self.clock()):
                raise Invalid("Outcome and its dependencies must be current and approved")
            obj = self.store.get(outcome["knowledge_id"])
            self._check_revision(obj, expected)
            if outcome["knowledge_revision"] != obj["revision"]:
                raise Invalid("Outcome was observed against another revision; review its applicability first")
            obj["confidence"] = round(max(0, min(1, obj["confidence"] + outcome["confidence_delta"])), 6)
            obj["confidence_rationale"] = outcome["delta_rationale"]
            evidence_field = "counterevidence_ids" if outcome["confidence_delta"] < 0 else "evidence_ids"
            opposite = "evidence_ids" if evidence_field == "counterevidence_ids" else "counterevidence_ids"
            if set(outcome["evidence_ids"]) & set(obj[opposite]):
                raise Invalid("Outcome evidence contradicts its existing evidence classification; revise explicitly")
            obj[evidence_field] = sorted(set(obj[evidence_field] + outcome["evidence_ids"]))
            obj["lifecycle"], obj["review"] = "in-review", None
            result = self._commit(obj, "apply-outcome", actor, reason)
            self.store.db.execute("INSERT INTO applied_outcomes VALUES (?, ?, ?, ?)",
                                  (outcome_id, outcome["revision"], obj["id"], self.clock()))
            return result

    def retrieve(self, query, domain, platform, audience=None, limit=10):
        if domain not in DOMAINS or not query.strip() or not platform.strip() or not 1 <= limit <= 100:
            raise Invalid("A query, known domain, platform, and limit from 1 to 100 are required")
        index = self.contracts.graph(self.store.all())
        now, tokens = self.clock(), set(re.findall(r"\w+", query.casefold()))
        results = []
        for obj in index.values():
            if obj["type"] != "knowledge" or not eligible(obj["id"], index, now):
                continue
            if domain not in obj["domains"] or obj["context"]["platform"].casefold() != platform.casefold():
                continue
            if audience and obj["context"]["audience"].casefold() != audience.casefold():
                continue
            text = " ".join([obj["title"], obj["claim"], obj["context"]["task"], *obj["context"]["constraints"]])
            score = len(tokens & set(re.findall(r"\w+", text.casefold())))
            if score == 0:
                continue
            evidence = [index[e] for e in obj["evidence_ids"] + obj["counterevidence_ids"]]
            sources = [index[s] for s in sorted({e["source_id"] for e in evidence})]
            # Keep approved conflicts visible even if another claim is now inactive.
            # Dropping them would silently erase dissent from retrieval.
            conflicts = [{**c, "current": eligible(c["id"], index, now),
                          "claims": [{"id": k, "claim": index[k]["claim"], "current": eligible(k, index, now)} for k in c["claim_ids"]]}
                         for c in index.values() if c["type"] == "conflict" and obj["id"] in c["claim_ids"]
                         and c["review"] and c["review"]["decision"] == "approved"]
            results.append({"knowledge": obj, "score": score, "evidence": evidence, "sources": sources, "conflicts": conflicts})
        return sorted(results, key=lambda r: (-r["score"], -r["knowledge"]["confidence"], r["knowledge"]["id"]))[:limit]

    def use_skill(self, skill_id):
        index = self.contracts.graph(self.store.all())
        skill = index.get(skill_id)
        if not skill or skill["type"] != "skill" or not eligible(skill_id, index, self.clock()):
            raise Invalid("Skill is not current or one of its knowledge dependencies needs review")
        evidence_ids = {e for k in skill["knowledge_ids"] for e in index[k]["evidence_ids"] + index[k]["counterevidence_ids"]}
        return {"skill": skill, "knowledge": [index[k] for k in skill["knowledge_ids"]],
                "evidence": [index[e] for e in sorted(evidence_ids)],
                "sources": [index[s] for s in sorted({index[e]["source_id"] for e in evidence_ids})],
                "conflicts": [o for o in index.values() if o["type"] == "conflict" and set(o["claim_ids"]) & set(skill["knowledge_ids"])],
                "execution": "Instructions returned for a human or tool adapter; no tool execution claimed"}
