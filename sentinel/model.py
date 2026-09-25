"""Offline schema validation, graph integrity, and publication policy."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parent.parent
KINDS = tuple(json.loads((ROOT / "brain/taxonomy.json").read_text())["object_types"])
DOMAINS = tuple(json.loads((ROOT / "brain/taxonomy.json").read_text())["domains"])


class Invalid(ValueError):
    """A user-facing contract, integrity, or workflow error."""


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def read_json(path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise Invalid(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                          object_pairs_hook=unique_pairs,
                          parse_constant=lambda x: (_ for _ in ()).throw(Invalid(f"Invalid number: {x}")))
    except (OSError, ValueError) as exc:
        raise Invalid(f"{path}: {exc}") from exc


class Contracts:
    def __init__(self):
        schemas = [read_json(p) for p in sorted((ROOT / "schemas").glob("*.json"))]
        for schema in schemas:
            Draft202012Validator.check_schema(schema)
        registry = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in schemas)
        checker = FormatChecker()

        @checker.checks("date-time", raises=(ValueError, TypeError))
        def valid_timestamp(value):
            if not isinstance(value, str):
                return True  # The JSON Schema type assertion handles non-strings.
            return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value)) and instant(value) is not None

        @checker.checks("uri", raises=ValueError)
        def valid_uri(value):
            if not isinstance(value, str):
                return True
            parts = urlsplit(value)
            return bool(parts.scheme and (parts.netloc or parts.path)) and not any(c.isspace() for c in value)

        self.validators = {
            kind: Draft202012Validator(next(s for s in schemas if s["$id"].endswith(f"/{kind}.schema.json")),
                                      registry=registry, format_checker=checker)
            for kind in KINDS
        }

    def validate(self, obj):
        if not isinstance(obj, dict) or obj.get("type") not in self.validators:
            raise Invalid("Object must declare a supported type")
        errors = sorted(self.validators[obj["type"]].iter_errors(obj), key=lambda e: str(list(e.path)))
        if errors:
            error = errors[0]
            raise Invalid(f"{obj.get('id', '?')} at {'.'.join(map(str, error.path)) or '<root>'}: {error.message}")
        if instant(obj["updated_at"]) < instant(obj["created_at"]):
            raise Invalid("updated_at precedes created_at")
        if "captured_at" in obj and instant(obj["captured_at"]) > instant(obj["updated_at"]):
            raise Invalid("Capture timestamp is later than the record update")
        review = obj["review"]
        if review:
            if not instant(obj["created_at"]) <= instant(review["at"]) <= instant(obj["updated_at"]):
                raise Invalid("Review timestamp is outside the object's lifetime")
            if obj["fixture"] != (review["actor_kind"] == "fixture"):
                raise Invalid("Fixture and human review identities cannot be mixed")
        if obj["lifecycle"] in ("draft", "in-review") and review is not None:
            if review["decision"] != "rejected" or obj["lifecycle"] != "draft":
                raise Invalid("Unpublished work cannot carry an approval")
        if obj["type"] == "knowledge" and set(obj["evidence_ids"]) & set(obj["counterevidence_ids"]):
            raise Invalid("Evidence cannot simultaneously support and contradict the same claim")

    def graph(self, objects):
        index = {}
        for obj in objects:
            self.validate(obj)
            if obj["id"] in index:
                raise Invalid(f"Duplicate ID: {obj['id']}")
            index[obj["id"]] = obj
        for obj in index.values():
            for target_id, kind in links(obj):
                target = index.get(target_id)
                if target is None or target["type"] != kind:
                    raise Invalid(f"{obj['id']}: missing or mistyped reference {target_id}")
                if target["fixture"] != obj["fixture"]:
                    raise Invalid("Fixture references cannot cross into live knowledge")
        for obj in index.values():
            if obj["type"] == "project-learning":
                if obj["knowledge_revision"] > index[obj["knowledge_id"]]["revision"]:
                    raise Invalid("Outcome references a future knowledge revision")
            if obj["lifecycle"] == "published":
                self.publish_policy(obj, index)
            visited, cursor = set(), obj
            while cursor.get("successor_id"):
                if cursor["id"] in visited:
                    raise Invalid("Supersession cycle")
                visited.add(cursor["id"])
                cursor = index[cursor["successor_id"]]
        return index

    def publish_policy(self, obj, index):
        """Structural trust checks; temporal eligibility is checked separately."""
        kind = obj["type"]
        if kind == "source" and obj["rights"]["status"] != "permitted":
            raise Invalid("Publication requires explicit permitted rights")
        if kind == "knowledge":
            if obj["confidence"] < 0.4:
                raise Invalid("Confidence below 0.4 remains a lead; revise or retire instead of publishing")
            sources = [index[index[e]["source_id"]] for e in obj["evidence_ids"]]
            strong = [s for s in sources if s["strength"] != "weak"]
            if not strong:
                raise Invalid("Weak sources alone cannot publish guidance")
            groups = {s["independence_group"] for s in strong}
            if obj["trust"] == "canonical" and len(groups) < 2:
                raise Invalid("Canonical knowledge needs two independent non-weak source groups")
            if obj["confidence"] >= 0.8 and len(groups) < 2:
                raise Invalid("High confidence needs independent corroboration")
        if kind == "experiment" and (obj["state"] != "completed" or obj["result"] is None):
            raise Invalid("A planned experiment is not a published result")

    def publication_gate(self, obj, index, now):
        self.publish_policy(obj, index)
        if instant(obj["review_due_at"]) <= instant(now):
            raise Invalid("Review due date must be in the future")
        for target_id, _ in links(obj):
            if target_id != obj.get("successor_id") and not eligible(target_id, index, now):
                raise Invalid(f"Dependency is not current, reviewed guidance: {target_id}")


def links(obj):
    result = []
    single = {"source_id": "source", "knowledge_id": "knowledge"}
    multiple = {"source_ids": "source", "knowledge_ids": "knowledge", "evidence_ids": "evidence",
                "counterevidence_ids": "evidence", "claim_ids": "knowledge"}
    for field, kind in single.items():
        if field in obj:
            result.append((obj[field], kind))
    for field, kind in multiple.items():
        result.extend((value, kind) for value in obj.get(field, []))
    if obj.get("result"):
        result.extend((value, "evidence") for value in obj["result"]["evidence_ids"])
    if obj.get("successor_id"):
        result.append((obj["successor_id"], obj["type"]))
    return result


def eligible(object_id, index, now, visiting=None):
    obj = index.get(object_id)
    if obj is None or obj["lifecycle"] != "published" or not obj["review"] or obj["review"]["decision"] != "approved":
        return False
    if instant(obj["review_due_at"]) <= instant(now):
        return False
    visiting = set() if visiting is None else visiting
    if object_id in visiting:
        return False
    return all(eligible(target, index, now, visiting | {object_id}) for target, _ in links(obj))


def load_directory(directory):
    paths = sorted(Path(directory).glob("*.json"))
    if not paths:
        raise Invalid(f"No JSON objects found in {directory}")
    return [read_json(path) for path in paths]
