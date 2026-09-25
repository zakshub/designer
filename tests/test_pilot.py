"""Real intake stays draft; approval simulations use fixture-only copies."""

import copy
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from sentinel.__main__ import main
from sentinel.engine import Brain
from sentinel.evaluation import evaluate
from sentinel.model import Contracts, Invalid, ROOT, load_directory, read_json
from sentinel.review import review_packet, review_queue
from sentinel.store import Store

PILOT = ROOT / "pilots/wcag-labels"
NOW = "2026-09-25T12:00:00Z"
SOURCE = "source_wcag22-20241212"
CLAIM = "knowledge_web-visible-label-name"


class PilotReviewTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:", fixture_mode=True)
        self.addCleanup(self.store.close)
        self.brain = Brain(self.store, clock=lambda: NOW)
        self.drafts = load_directory(PILOT / "intake")
        # Never simulate a human attestation on real/live records.
        for obj in self.drafts:
            obj["fixture"] = True
        self.brain.ingest(self.drafts, "fixture-author", "Temporary copy for workflow tests only")

    def publish_all(self):
        for kind in ("source", "evidence", "knowledge", "skill"):
            for obj in self.store.all():
                if obj["type"] != kind:
                    continue
                if kind == "source":
                    obj = self.brain.revise(obj["id"], {"rights": {"status": "permitted", "note": "Simulated permission for fixture test only"}},
                                            "fixture-reviewer", "Simulation", obj["revision"])
                obj = self.brain.submit(obj["id"], "fixture-reviewer", "Simulation", obj["revision"])
                self.brain.review(obj["id"], "fixture-reviewer", "Simulation", obj["revision"])

    def suite(self):
        return read_json(PILOT / "retrieval-suite.json")

    def test_checked_in_intake_is_real_but_unapproved(self):
        originals = load_directory(PILOT / "intake")
        Contracts().graph(originals)
        self.assertEqual(len(originals), 10)
        for obj in originals:
            self.assertFalse(obj["fixture"])
            self.assertIsNone(obj["review"])
            self.assertEqual(obj["lifecycle"], "draft")
        sources = [o for o in originals if o["type"] == "source"]
        self.assertEqual({s["independence_group"] for s in sources}, {"w3c-wcag"})
        self.assertTrue(all(s["locator"].startswith("https://www.w3.org/") for s in sources))

    def test_queue_orders_dependencies_and_explains_rights(self):
        queue = review_queue(self.brain)
        self.assertEqual(queue["pending_count"], 10)
        self.assertEqual(queue["ready_for_approval"], 0)
        self.assertEqual([i["type"] for i in queue["items"][:3]], ["source"] * 3)
        self.assertEqual(queue["items"][-1]["type"], "skill")
        self.assertIn("rights", queue["items"][0]["publication_blockers"][0])

    def test_review_packet_contains_transitive_provenance(self):
        packet = review_packet(self.brain, CLAIM)
        self.assertEqual(len(packet["dependencies"]), 4)
        self.assertEqual({d["object"]["type"] for d in packet["dependencies"]}, {"source", "evidence"})
        self.assertEqual(packet["object"]["revision"], 1)
        self.assertFalse(packet["summary"]["ready_for_approval"])
        self.assertEqual(len(packet["summary"]["publication_blockers"]), 2)

    def test_packet_and_queue_do_not_mutate(self):
        before, writes = self.store.all(), self.store.db.total_changes
        review_packet(self.brain, CLAIM)
        review_queue(self.brain)
        self.assertEqual(self.store.all(), before)
        self.assertEqual(self.store.db.total_changes, writes)

    def test_ready_is_not_approval(self):
        obj = self.brain.revise(SOURCE, {"rights": {"status": "permitted", "note": "Fixture-only simulated permission"}},
                                "fixture-reviewer", "Simulation", 1)
        self.brain.submit(SOURCE, "fixture-reviewer", "Simulation", obj["revision"])
        packet = review_packet(self.brain, SOURCE)
        self.assertTrue(packet["summary"]["ready_for_approval"])
        self.assertEqual(packet["summary"]["next_action"], "human-review")
        self.assertEqual(self.store.get(SOURCE)["lifecycle"], "in-review")
        self.assertIsNone(self.store.get(SOURCE)["review"])

    def test_queue_uses_actual_approval_gates(self):
        self.brain.submit(SOURCE, "fixture-reviewer", "Simulation", 1)
        reasons = review_packet(self.brain, SOURCE)["summary"]["publication_blockers"]
        with self.assertRaises(Invalid) as error:
            self.brain.review(SOURCE, "fixture-reviewer", "Simulation", 2)
        self.assertEqual(str(error.exception), "; ".join(reasons))

    def test_current_records_leave_queue(self):
        self.publish_all()
        self.assertEqual(review_queue(self.brain)["pending_count"], 0)

    def test_changed_source_reopens_dependent_review_work(self):
        self.publish_all()
        obj = self.store.get(SOURCE)
        self.brain.revise(SOURCE, {"title": "Updated source context"}, "fixture-reviewer", "Simulation", obj["revision"])
        item = next(i for i in review_queue(self.brain)["items"] if i["id"] == CLAIM)
        self.assertEqual(item["lifecycle"], "stale")
        self.assertEqual(item["next_action"], "revise-and-resubmit")

    def test_expiry_requires_review_without_sweep(self):
        self.publish_all()
        self.brain.clock = lambda: "2026-12-25T00:00:00Z"
        packet = review_packet(self.brain, CLAIM)
        self.assertFalse(packet["summary"]["current"])
        self.assertIn("future", packet["summary"]["publication_blockers"][0])

    def test_unknown_packet_id(self):
        with self.assertRaises(Invalid):
            review_packet(self.brain, "knowledge_absent")

    def test_pending_suite_is_blocked_not_false_success(self):
        result = evaluate(self.brain, self.suite())
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["counts"], {"pass": 3, "fail": 0, "blocked": 5})

    def test_simulated_approved_suite_matches_expectations(self):
        self.publish_all()
        result = evaluate(self.brain, self.suite())
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["counts"], {"pass": 8, "fail": 0, "blocked": 0})
        self.assertEqual(result["judgments"], "proposed")

    def test_wrong_retrieval_expectation_is_failure(self):
        self.publish_all()
        suite = self.suite()
        suite["cases"][0]["query"] = "volumetric nebula"
        result = evaluate(self.brain, suite)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["cases"][0]["missing_ids"], [CLAIM])

    def test_forbidden_hits_are_failures(self):
        self.publish_all()
        suite = self.suite()
        suite["cases"] = [suite["cases"][-1]]
        suite["cases"][0]["query"] = "labels"
        result = evaluate(self.brain, suite)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(len(result["cases"][0]["forbidden_hits"]), 2)

    def test_evaluation_does_not_change_history_or_confidence(self):
        self.publish_all()
        before, history, writes = self.store.all(), self.store.history(CLAIM), self.store.db.total_changes
        evaluate(self.brain, self.suite())
        self.assertEqual(self.store.all(), before)
        self.assertEqual(self.store.history(CLAIM), history)
        self.assertEqual(self.store.db.total_changes, writes)
        self.assertFalse(self.store.db.in_transaction)

    def test_invalid_suites_fail_and_release_snapshot(self):
        cases = []
        empty = self.suite()
        empty["cases"] = []
        cases.append(empty)
        duplicate = self.suite()
        duplicate["cases"].append(copy.deepcopy(duplicate["cases"][0]))
        cases.append(duplicate)
        for key, value in (("limit", 0), ("limit", True), ("limit", 101), ("query", " "),
                           ("domain", "made-up"), ("expected_ids", ["knowledge_missing"]),
                           ("forbidden_ids", [CLAIM]), ("extra", "unsupported")):
            suite = self.suite()
            suite["cases"][0][key] = value
            cases.append(suite)
        for suite in cases:
            with self.subTest(suite=suite):
                with self.assertRaises(Invalid):
                    evaluate(self.brain, suite)
                self.assertFalse(self.store.db.in_transaction)

    def test_insufficient_case_limit_rejected(self):
        suite = self.suite()
        suite["cases"][3]["limit"] = 1
        with self.assertRaises(Invalid):
            evaluate(self.brain, suite)

    def test_w3c_pages_do_not_qualify_as_independent_corroboration(self):
        self.publish_all()
        obj = self.store.get(CLAIM)
        obj = self.brain.revise(CLAIM, {"trust": "canonical"}, "fixture-reviewer", "Simulation", obj["revision"])
        obj = self.brain.submit(CLAIM, "fixture-reviewer", "Simulation", obj["revision"])
        self.assertIn("independent", review_packet(self.brain, CLAIM)["summary"]["publication_blockers"][0])
        with self.assertRaises(Invalid):
            self.brain.review(CLAIM, "fixture-reviewer", "Simulation", obj["revision"])


class PilotCliTests(unittest.TestCase):
    def test_live_intake_and_blocked_exit_without_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "live.sqlite3")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--db", path, "ingest", str(PILOT / "intake"), "--actor", "codex-intake", "--reason", "Source-grounded drafts"]), 0)
                self.assertEqual(main(["--db", path, "review-queue"]), 0)
                self.assertEqual(main(["--db", path, "review-packet", CLAIM]), 0)
                self.assertEqual(main(["--db", path, "evaluate", str(PILOT / "retrieval-suite.json")]), 2)
            store = Store(path)
            try:
                self.assertTrue(all(o["review"] is None and o["lifecycle"] == "draft" for o in store.all()))
                self.assertEqual(len(store.history(CLAIM)), 1)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
