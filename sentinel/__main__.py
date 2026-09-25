"""Run `python -m sentinel --help` for the local backend interface."""

import argparse
import json
import sqlite3
import sys
from collections import Counter

from .engine import Brain
from .model import Contracts, Invalid, ROOT, eligible, load_directory, read_json
from .store import Store


def demo(brain):
    """Complete synthetic learning cycle; never attests real human review."""
    if not brain.store.fixture_mode or brain.store.all():
        raise Invalid("Demo needs an empty fixture-mode database")
    actor, reason = "simulated-reviewer", "Simulated review for executable acceptance demonstration."
    brain.ingest(load_directory(ROOT / "examples"), actor, "Load fictional draft fixtures")
    order = ["source", "evidence", "knowledge", "expert-profile", "reference", "skill", "experiment", "conflict", "project-learning"]
    for kind in order:
        for obj in brain.store.all():
            if obj["type"] != kind:
                continue
            if kind == "project-learning":
                obj = brain.revise(obj["id"], {"knowledge_revision": brain.store.get(obj["knowledge_id"])["revision"]},
                                   actor, "Pin the exact decision revision used in the simulated project", obj["revision"])
            obj = brain.submit(obj["id"], actor, reason, obj["revision"])
            brain.review(obj["id"], actor, reason, obj["revision"])
    before = brain.retrieve("explicit action labels", "ui", "mobile")
    knowledge_id = "knowledge_explicit-labels-mobile"
    obj = brain.apply_outcome("project-learning_explicit-labels-mobile", actor,
                              "Apply one reviewed simulated outcome; revised guidance awaits approval", brain.store.get(knowledge_id)["revision"])
    pending = brain.retrieve("explicit action labels", "ui", "mobile")
    obj = brain.review(knowledge_id, actor, reason, obj["revision"])
    after = brain.retrieve("explicit action labels", "ui", "mobile")
    brain.retire(knowledge_id, actor, "Demonstrate retention policy: remove simulated guidance from active use", obj["revision"])
    retired = brain.retrieve("explicit action labels", "ui", "mobile")
    return {"mode": "synthetic fixtures only", "objects": len(brain.store.all()),
            "before": [r["knowledge"]["id"] for r in before],
            "during_review": [r["knowledge"]["id"] for r in pending],
            "after_review": [r["knowledge"]["id"] for r in after],
            "after_retirement": [r["knowledge"]["id"] for r in retired],
            "updated_confidence": obj["confidence"], "history": brain.store.history(knowledge_id)}


def parser():
    p = argparse.ArgumentParser(description="Sentinel: local reviewed design knowledge backend")
    p.add_argument("--db", default="data/sentinel.sqlite3")
    p.add_argument("--fixture-mode", action="store_true", help="Use a separate database that accepts fictional records only")
    sub = p.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="Validate schemas and a directory of JSON objects")
    validate.add_argument("directory", nargs="?", default=str(ROOT / "examples"))
    sub.add_parser("demo", help="Run a synthetic learning cycle in an empty fixture-mode database")
    sub.add_parser("status")
    sub.add_parser("export", help="Write all current records as JSON to stdout")
    q = sub.add_parser("backup", help="Save a consistent database copy including history; refuses overwrite")
    q.add_argument("destination")
    for name in ("show", "history", "use-skill"):
        q = sub.add_parser(name)
        q.add_argument("id")
    q = sub.add_parser("retrieve")
    q.add_argument("query")
    q.add_argument("--domain", required=True)
    q.add_argument("--platform", required=True)
    q.add_argument("--audience")
    q.add_argument("--limit", type=int, default=10)
    for name in ("ingest", "revise", "submit", "review", "retire", "apply-outcome", "sweep"):
        q = sub.add_parser(name)
        q.add_argument("--actor", required=True)
        q.add_argument("--reason", required=True)
        if name == "ingest":
            q.add_argument("directory")
        elif name != "sweep":
            q.add_argument("id")
            q.add_argument("--expected", type=int, required=True, help="Current object revision (knowledge revision for apply-outcome)")
        if name == "revise":
            q.add_argument("changes", help="JSON file with content fields to change")
        if name == "review":
            q.add_argument("--decision", choices=["approve", "reject"], required=True)
        if name == "retire":
            q.add_argument("--successor")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    store = None
    try:
        if args.command == "validate":
            contracts = Contracts()
            objects = contracts.graph(load_directory(args.directory))
            result = {"valid": True, "objects": len(objects), "schemas": len(contracts.validators),
                      "types": dict(Counter(o["type"] for o in objects.values()))}
        else:
            store = Store(args.db, args.fixture_mode)
            brain, command = Brain(store), args.command
            if command == "demo":
                result = demo(brain)
            elif command == "status":
                index = brain.contracts.graph(store.all())
                result = {"mode": "fixture" if store.fixture_mode else "live", "objects": len(index),
                          "lifecycle": dict(Counter(o["lifecycle"] for o in index.values())),
                          "eligible": sum(eligible(k, index, brain.clock()) for k in index)}
            elif command == "export":
                result = store.all()
            elif command == "backup":
                result = store.backup(args.destination)
            elif command == "show":
                result = store.get(args.id)
            elif command == "history":
                result = store.history(args.id)
            elif command == "use-skill":
                result = brain.use_skill(args.id)
            elif command == "retrieve":
                result = brain.retrieve(args.query, args.domain, args.platform, args.audience, args.limit)
            elif command == "ingest":
                result = brain.ingest(load_directory(args.directory), args.actor, args.reason)
            elif command == "sweep":
                result = brain.sweep(args.actor, args.reason)
            elif command == "revise":
                result = brain.revise(args.id, read_json(args.changes), args.actor, args.reason, args.expected)
            elif command == "submit":
                result = brain.submit(args.id, args.actor, args.reason, args.expected)
            elif command == "review":
                result = brain.review(args.id, args.actor, args.reason, args.expected, args.decision == "approve")
            elif command == "retire":
                result = brain.retire(args.id, args.actor, args.reason, args.expected, args.successor)
            elif command == "apply-outcome":
                result = brain.apply_outcome(args.id, args.actor, args.reason, args.expected)
        print(json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False))
        return 0
    except (Invalid, sqlite3.Error, OSError) as exc:
        print(f"Sentinel: {exc}", file=sys.stderr)
        return 1
    finally:
        if store:
            store.close()


if __name__ == "__main__":
    sys.exit(main())
