import copy
import io
import json
import tempfile
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path

from sentinel.__main__ import demo, main
from sentinel.engine import Brain
from sentinel.model import Contracts, Invalid, KINDS, ROOT, load_directory, read_json
from sentinel.store import Store

NOW = "2026-09-25T12:00:00Z"
K = "knowledge_explicit-labels-mobile"
K2 = "knowledge_compact-labels-mobile"
S = "source_accessibility-guidance"
E = "evidence_clear-labels-mobile"
O = "project-learning_explicit-labels-mobile"


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contracts = Contracts()

    def setUp(self):
        self.objects = load_directory(ROOT / "examples")
        self.index = {o["id"]: o for o in self.objects}

    def test_every_kind_has_valid_example(self):
        self.assertEqual(set(KINDS), {o["type"] for o in self.objects})
        self.assertEqual(len(self.contracts.graph(self.objects)), 13)

    def test_bad_values_rejected(self):
        mutations = [
            ("id", "source_wrong-type"), ("domains", ["invented"]), ("confidence", 1.1),
            ("confidence", -0.1), ("confidence", "0.5"), ("revision", 0), ("revision", True),
            ("schema_version", "2.0.0"), ("claim", "   "), ("created_at", "yesterday"),
            ("updated_at", "2020-01-01T00:00:00Z"), ("review_due_at", "2027-02-30T00:00:00Z"),
            ("evidence_ids", []), ("evidence_ids", [E, E]), ("evidence_ids", [S]),
            ("unknown", "x"), ("lifecycle", "trusted"), ("fixture", "false"),
        ]
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                obj = copy.deepcopy(self.index[K])
                obj[key] = value
                with self.assertRaises(Invalid):
                    self.contracts.validate(obj)

    def test_publication_requires_review(self):
        self.index[K]["lifecycle"] = "published"
        with self.assertRaises(Invalid):
            self.contracts.validate(self.index[K])

    def test_missing_reference(self):
        self.index[K]["evidence_ids"] = ["evidence_missing"]
        with self.assertRaisesRegex(Invalid, "missing or mistyped"):
            self.contracts.graph(self.objects)

    def test_duplicate_id(self):
        with self.assertRaisesRegex(Invalid, "Duplicate ID"):
            self.contracts.graph(self.objects + [self.objects[0]])

    def test_fixture_reference_boundary(self):
        self.index[E]["fixture"] = False
        with self.assertRaisesRegex(Invalid, "Fixture references"):
            self.contracts.graph(self.objects)

    def test_future_outcome_revision(self):
        self.index[O]["knowledge_revision"] = 999
        with self.assertRaisesRegex(Invalid, "future"):
            self.contracts.graph(self.objects)

    def test_conflict_needs_distinct_claims_and_resolution(self):
        conflict = self.index["conflict_label-density"]
        conflict["claim_ids"] = [K, K]
        with self.assertRaises(Invalid):
            self.contracts.validate(conflict)
        conflict["claim_ids"] = [K, K2]
        conflict["status"] = "resolved"
        with self.assertRaises(Invalid):
            self.contracts.validate(conflict)

    def test_completed_experiment_needs_result(self):
        obj = self.index["experiment_explicit-labels-mobile"]
        obj["result"] = None
        with self.assertRaises(Invalid):
            self.contracts.validate(obj)

    def test_retirement_reason_required(self):
        obj = self.index[K]
        obj["lifecycle"] = "retired"
        with self.assertRaises(Invalid):
            self.contracts.validate(obj)

    def test_same_evidence_cannot_support_and_contradict(self):
        self.index[K]["counterevidence_ids"] = [E]
        with self.assertRaises(Invalid):
            self.contracts.validate(self.index[K])

    def test_json_duplicate_keys_and_nonfinite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            for text in ('{"id":"a","id":"b"}', '{"confidence": NaN}', '{"confidence": Infinity}', '{broken'):
                path.write_text(text)
                with self.assertRaises(Invalid):
                    read_json(path)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:", fixture_mode=True)
        self.addCleanup(self.store.close)
        self.now = NOW
        self.brain = Brain(self.store, clock=lambda: self.now)
        self.brain.ingest(load_directory(ROOT / "examples"), "fixture-author", "Test ingestion")

    def publish(self, object_id):
        obj = self.store.get(object_id)
        obj = self.brain.submit(object_id, "test-reviewer", "Review fixture", obj["revision"])
        return self.brain.review(object_id, "test-reviewer", "Simulated review passed", obj["revision"])

    def publish_base(self):
        for kind in ("source", "evidence", "knowledge"):
            for obj in self.store.all():
                if obj["type"] == kind:
                    self.publish(obj["id"])

    def revise(self, object_id, changes):
        return self.brain.revise(object_id, changes, "test-reviewer", "Correction", self.store.get(object_id)["revision"])

    def publish_outcome(self, delta=0.1):
        self.revise(O, {"knowledge_revision": self.store.get(K)["revision"], "confidence_delta": delta})
        return self.publish(O)

    def retrieve(self):
        return self.brain.retrieve("explicit action labels", "ui", "mobile")

    def test_drafts_never_retrieved(self):
        self.assertEqual(self.retrieve(), [])

    def test_dependency_publication_order(self):
        obj = self.brain.submit(K, "reviewer", "Review", 1)
        with self.assertRaisesRegex(Invalid, "Dependency"):
            self.brain.review(K, "reviewer", "Review", obj["revision"])
        self.assertEqual(self.store.get(K)["revision"], 2)
        self.assertEqual(len(self.store.history(K)), 2)

    def test_publication_retrieval_provenance_context(self):
        self.publish_base()
        results = self.retrieve()
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0]["evidence"])
        self.assertTrue(results[0]["sources"])
        self.assertEqual(self.brain.retrieve("labels", "ui", "desktop"), [])
        self.assertEqual(self.brain.retrieve("labels", "ui", "mobile", "unrelated audience"), [])
        self.assertEqual(self.brain.retrieve("unmatchedtoken", "ui", "mobile"), [])
        self.assertEqual(results, self.retrieve())

    def test_conflicts_remain_visible_after_other_claim_retired(self):
        self.publish_base()
        self.publish("conflict_label-density")
        self.brain.retire(K2, "reviewer", "Outdated", 3)
        result = self.retrieve()[0]
        self.assertEqual(result["knowledge"]["id"], K)
        self.assertFalse(result["conflicts"][0]["current"])
        self.assertEqual(len(result["conflicts"][0]["claims"]), 2)

    def test_rejection_and_resubmission(self):
        obj = self.brain.submit(S, "reviewer", "Review", 1)
        obj = self.brain.review(S, "reviewer", "Missing context", obj["revision"], approve=False)
        self.assertEqual(obj["lifecycle"], "draft")
        self.assertEqual(obj["review"]["decision"], "rejected")
        self.assertEqual(self.publish(S)["lifecycle"], "published")

    def test_illegal_transitions(self):
        with self.assertRaises(Invalid):
            self.brain.review(S, "reviewer", "Review", 1)
        self.publish(S)
        with self.assertRaises(Invalid):
            self.brain.submit(S, "reviewer", "Review", 3)

    def test_review_attestation_cannot_be_injected(self):
        with self.assertRaises(Invalid):
            self.revise(S, {"review": {"decision": "approved"}})
        with self.assertRaises(Invalid):
            self.revise(S, {"fixture": False})

    def test_unknown_rights_blocks_publication(self):
        self.revise(S, {"rights": {"status": "unknown", "note": "Not verified"}})
        with self.assertRaisesRegex(Invalid, "rights"):
            self.publish(S)

    def test_weak_source_cannot_publish_claim(self):
        self.revise(S, {"strength": "weak"})
        self.publish(S)
        self.publish(E)
        with self.assertRaisesRegex(Invalid, "Weak"):
            self.publish(K)

    def test_single_source_canonical_blocked(self):
        self.publish(S)
        self.publish(E)
        self.revise(K, {"trust": "canonical"})
        with self.assertRaisesRegex(Invalid, "independent"):
            self.publish(K)

    def test_high_confidence_needs_corroboration(self):
        self.publish(S)
        self.publish(E)
        self.revise(K, {"confidence": 0.9})
        with self.assertRaisesRegex(Invalid, "confidence"):
            self.publish(K)

    def test_independent_sources_allow_canonical(self):
        self.publish_base()
        self.revise(K, {"evidence_ids": [E, "evidence_compact-labels-mobile"], "trust": "canonical", "confidence": 0.85})
        self.assertEqual(self.publish(K)["trust"], "canonical")

    def test_same_group_is_not_independent(self):
        self.revise("source_independent-lab", {"independence_group": "fixture-lab-a"})
        self.publish_base()
        self.revise(K, {"evidence_ids": [E, "evidence_compact-labels-mobile"], "trust": "canonical"})
        with self.assertRaisesRegex(Invalid, "independent"):
            self.publish(K)

    def test_outcome_update_requires_second_review_and_is_idempotent(self):
        self.publish_base()
        self.publish_outcome()
        obj = self.brain.apply_outcome(O, "reviewer", "Use reviewed observation", 3)
        self.assertAlmostEqual(obj["confidence"], 0.65)
        self.assertEqual(obj["lifecycle"], "in-review")
        self.assertNotIn(K, [r["knowledge"]["id"] for r in self.retrieve()])
        with self.assertRaisesRegex(Invalid, "already"):
            self.brain.apply_outcome(O, "reviewer", "Repeat", obj["revision"])
        self.brain.review(K, "reviewer", "Review confidence update", obj["revision"])
        self.assertIn(K, [r["knowledge"]["id"] for r in self.retrieve()])

    def test_negative_outcome_records_counterevidence(self):
        self.publish_base()
        self.publish_outcome(-0.1)
        obj = self.brain.apply_outcome(O, "reviewer", "Evidence weakens the claim", 3)
        self.assertAlmostEqual(obj["confidence"], 0.45)
        self.assertEqual(obj["counterevidence_ids"], ["evidence_outcome-mobile"])

    def test_unreviewed_outcome_rejected(self):
        self.publish_base()
        with self.assertRaisesRegex(Invalid, "approved"):
            self.brain.apply_outcome(O, "reviewer", "Apply", 3)

    def test_outcome_wrong_revision_rejected(self):
        self.publish_base()
        self.revise(K, {"claim": "Clarified action-label guidance"})
        self.publish(K)
        self.revise(O, {"knowledge_revision": 3})  # A previously published revision.
        self.publish(O)
        with self.assertRaisesRegex(Invalid, "another revision"):
            self.brain.apply_outcome(O, "reviewer", "Apply", self.store.get(K)["revision"])

    def test_outcome_cannot_claim_use_of_unpublished_revision(self):
        self.publish_base()
        with self.assertRaisesRegex(Invalid, "published historical"):
            self.publish(O)

    def test_revision_conflict_preserves_history(self):
        self.publish(S)
        with self.assertRaisesRegex(Invalid, "Revision conflict"):
            self.brain.revise(S, {"title": "Changed"}, "reviewer", "Edit", 1)
        self.assertEqual(len(self.store.history(S)), 3)

    def test_failed_batch_is_atomic(self):
        originals = self.store.all()
        a = copy.deepcopy(originals[-1])
        a["id"] = "source_new-one"
        b = copy.deepcopy(a)
        b["id"] = "source_new-two"
        b["title"] = ""
        with self.assertRaises(Invalid):
            self.brain.ingest([a, b], "author", "Batch")
        self.assertEqual(originals, self.store.all())

    def test_failed_revision_is_atomic(self):
        before = self.store.get(K)
        with self.assertRaises(Invalid):
            self.revise(K, {"evidence_ids": ["evidence_missing"]})
        self.assertEqual(before, self.store.get(K))
        self.assertEqual(len(self.store.history(K)), 1)

    def test_expiry_transitive_without_sweep(self):
        self.revise(S, {"review_due_at": "2026-09-26T00:00:00Z"})
        self.publish_base()
        self.now = "2026-09-26T00:00:00Z"
        self.assertNotIn(K, [r["knowledge"]["id"] for r in self.retrieve()])
        self.brain.sweep("operator", "Review due")
        self.assertEqual(self.store.get(S)["lifecycle"], "stale")
        self.assertEqual(self.store.get(K)["lifecycle"], "stale")
        self.assertEqual(self.brain.sweep("operator", "Review due"), [])

    def test_source_change_requires_downstream_review(self):
        self.publish_base()
        self.revise(S, {"title": "Corrected source"})
        self.assertEqual(self.store.get(E)["lifecycle"], "stale")
        self.assertEqual(self.store.get(K)["lifecycle"], "stale")
        self.publish(S)
        self.assertNotIn(K, [r["knowledge"]["id"] for r in self.retrieve()])

    def test_retirement_preserves_history_and_recovery_requires_review(self):
        self.publish_base()
        obj = self.brain.retire(K, "reviewer", "Withdraw guidance", 3)
        self.assertEqual(obj["lifecycle"], "retired")
        self.assertEqual(len(self.store.history(K)), 4)
        self.revise(K, {"claim": "Corrected original claim"})
        self.assertNotIn(K, [r["knowledge"]["id"] for r in self.retrieve()])
        self.publish(K)
        self.assertEqual(self.store.get(K)["lifecycle"], "published")

    def test_supersession(self):
        self.publish_base()
        self.brain.retire(K, "reviewer", "New guidance replaces old", 3, K2)
        self.assertEqual(self.store.get(K)["successor_id"], K2)
        with self.assertRaisesRegex(Invalid, "immutable"):
            self.revise(K, {"title": "Cannot edit"})
        with self.assertRaises(Invalid):
            self.brain.retire(K2, "reviewer", "Cycle", 3, K)

    def test_skill_is_blocked_when_knowledge_changes(self):
        self.publish_base()
        self.publish("skill_review-action-labels")
        self.assertEqual(len(self.brain.use_skill("skill_review-action-labels")["knowledge"]), 1)
        self.revise(K, {"claim": "Needs another review"})
        with self.assertRaises(Invalid):
            self.brain.use_skill("skill_review-action-labels")

    def test_empty_actor_is_rejected(self):
        with self.assertRaises(Invalid):
            self.brain.submit(S, " ", "Review", 1)

    def test_empty_query_is_rejected(self):
        with self.assertRaises(Invalid):
            self.brain.retrieve("", "ui", "mobile")


class PersistenceAndCliTests(unittest.TestCase):
    def test_backup_restores_history_and_outcome_deduplication(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            original = Store(Path(folder) / "original.sqlite3", fixture_mode=True)
            stack.callback(original.close)
            demo(Brain(original, clock=lambda: NOW))
            destination = Path(folder) / "snapshot.sqlite3"
            original.backup(destination)
            with self.assertRaises(Invalid):
                original.backup(destination)
            restored = Store(destination, fixture_mode=True)
            stack.callback(restored.close)
            self.assertEqual(original.all(), restored.all())
            self.assertEqual(original.history(K), restored.history(K))
            self.assertEqual(restored.db.execute("SELECT COUNT(*) FROM applied_outcomes").fetchone()[0], 1)

    def test_two_connections_reject_stale_revision(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            path = Path(folder) / "shared.sqlite3"
            one, two = Store(path, True), Store(path, True)
            stack.callback(one.close)
            stack.callback(two.close)
            a, b = Brain(one, clock=lambda: NOW), Brain(two, clock=lambda: NOW)
            a.ingest(load_directory(ROOT / "examples"), "author", "Ingest")
            a.revise(S, {"title": "First editor"}, "a", "Edit", 1)
            with self.assertRaisesRegex(Invalid, "Revision conflict"):
                b.revise(S, {"title": "Second editor"}, "b", "Edit", 1)
            self.assertEqual(two.get(S)["title"], "First editor")

    def test_restart_and_mode_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "brain.sqlite3"
            store = Store(path, fixture_mode=True)
            Brain(store, clock=lambda: NOW).ingest(load_directory(ROOT / "examples"), "author", "Fixture ingestion")
            store.close()
            with self.assertRaisesRegex(Invalid, "mode"):
                Store(path)
            reopened = Store(path, fixture_mode=True)
            try:
                self.assertEqual(len(reopened.all()), 13)
                self.assertEqual(len(reopened.history(K)), 1)
            finally:
                reopened.close()

    def test_live_store_rejects_fixtures(self):
        store = Store(":memory:")
        try:
            with self.assertRaisesRegex(Invalid, "mismatch"):
                Brain(store, clock=lambda: NOW).ingest(load_directory(ROOT / "examples"), "author", "Wrong environment")
            self.assertEqual(store.all(), [])
        finally:
            store.close()

    def test_cli_validate_and_failure_exit_code(self):
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(["validate"]), 0)
        self.assertEqual(json.loads(out.getvalue())["objects"], 13)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(["validate", "missing-directory"]), 1)

    def test_full_cycle(self):
        store = Store(":memory:", fixture_mode=True)
        try:
            result = demo(Brain(store, clock=lambda: NOW))
            self.assertIn(K, result["before"])
            self.assertNotIn(K, result["during_review"])
            self.assertIn(K, result["after_review"])
            self.assertNotIn(K, result["after_retirement"])
            self.assertEqual(result["updated_confidence"], 0.65)
            self.assertEqual([h["action"] for h in result["history"]],
                             ["ingest", "submit", "approve", "apply-outcome", "approve", "retired"])
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
