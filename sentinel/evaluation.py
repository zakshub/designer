"""Read-only retrieval evaluation against explicit, versioned expectations."""

from jsonschema import Draft202012Validator

from .model import DOMAINS, Invalid, eligible

TEXT = {"type": "string", "minLength": 1, "pattern": "\\S"}
IDS = {"type": "array", "uniqueItems": True,
       "items": {"type": "string", "pattern": "^knowledge_[a-z0-9]+(?:-[a-z0-9]+)*$"}}
SUITE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["schema_version", "id", "purpose", "judgments", "cases"],
    "properties": {
        "schema_version": {"const": "1.0.0"}, "id": TEXT, "purpose": TEXT,
        "judgments": {"const": "proposed"},
        "cases": {"type": "array", "minItems": 1, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "query", "domain", "platform", "expected_ids", "forbidden_ids", "limit"],
            "properties": {"id": TEXT, "query": TEXT, "domain": {"enum": list(DOMAINS)}, "platform": TEXT,
                           "audience": TEXT, "expected_ids": IDS, "forbidden_ids": IDS,
                           "limit": {"type": "integer", "minimum": 1, "maximum": 100}}
        }}
    }
}


def validate_suite(suite, index):
    errors = list(Draft202012Validator(SUITE_SCHEMA).iter_errors(suite))
    if errors:
        raise Invalid(f"Invalid evaluation suite: {errors[0].message}")
    seen = set()
    for case in suite["cases"]:
        if case["id"] in seen:
            raise Invalid(f"Duplicate evaluation case ID: {case['id']}")
        seen.add(case["id"])
        expected, forbidden = set(case["expected_ids"]), set(case["forbidden_ids"])
        if expected & forbidden:
            raise Invalid("An expected ID cannot also be forbidden")
        if not expected and not forbidden:
            raise Invalid("Each case must declare expected or forbidden knowledge")
        if len(expected) > case["limit"]:
            raise Invalid("Case limit is smaller than its expected result set")
        for object_id in expected | forbidden:
            if object_id not in index or index[object_id]["type"] != "knowledge":
                raise Invalid(f"Unknown evaluation knowledge ID: {object_id}")


def evaluate(brain, suite):
    # A deferred read transaction gives every query the same database snapshot.
    with brain.store.snapshot():
        index = brain.contracts.graph(brain.store.all())
        validate_suite(suite, index)
        now, cases = brain.clock(), []
        for case in suite["cases"]:
            unavailable = [key for key in case["expected_ids"] if not eligible(key, index, now)]
            if unavailable:
                cases.append({"id": case["id"], "status": "blocked", "unavailable_ids": unavailable,
                              "reason": "Expected guidance or its dependencies are not currently approved; no relevance result claimed."})
                continue
            results = brain.retrieve(case["query"], case["domain"], case["platform"], case.get("audience"), case["limit"])
            actual = [r["knowledge"]["id"] for r in results]
            expected, forbidden = set(case["expected_ids"]), set(case["forbidden_ids"])
            missing = sorted(expected - set(actual))
            forbidden_hits = sorted(forbidden & set(actual))
            unexpected = sorted(set(actual) - expected)
            passed = not missing and not forbidden_hits and not unexpected
            cases.append({"id": case["id"], "status": "pass" if passed else "fail",
                          "actual_ids": actual, "missing_ids": missing, "forbidden_hits": forbidden_hits,
                          "unexpected_ids": unexpected,
                          "recall_at_limit": len(expected & set(actual)) / len(expected) if expected else None,
                          "precision_at_limit": len(expected & set(actual)) / len(actual) if actual else None})
        counts = {state: sum(case["status"] == state for case in cases) for state in ("pass", "fail", "blocked")}
        status = "fail" if counts["fail"] else "blocked" if counts["blocked"] else "pass"
        return {"suite_id": suite["id"], "status": status, "judgments": suite["judgments"], "as_of": now,
                "mode": "fixture" if brain.store.fixture_mode else "live", "counts": counts,
                "knowledge_revisions": {key: obj["revision"] for key, obj in index.items() if obj["type"] == "knowledge"},
                "cases": cases, "note": "Tests proposed retrieval expectations only; does not approve knowledge or measure user outcomes."}
