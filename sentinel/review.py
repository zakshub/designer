"""Read-only reviewer packets and dependency-ordered work queues."""

from .model import Invalid, eligible, links


def approval_blockers(brain, obj, index, now):
    reasons = brain.contracts.publication_blockers(obj, index, now)
    if obj["type"] == "project-learning":
        used = next((h["body"] for h in brain.store.history(obj["knowledge_id"])
                     if h["revision"] == obj["knowledge_revision"]), None)
        if not used or used["lifecycle"] != "published":
            reasons.append("Project outcome must cite a published historical knowledge revision")
    return reasons


def dependency_depth(object_id, index, visiting=None):
    visiting = set() if visiting is None else visiting
    if object_id in visiting:
        return 0  # Inactive successor chains cannot make queue ordering recurse forever.
    return 1 + max((dependency_depth(target, index, visiting | {object_id})
                    for target, _ in links(index[object_id])), default=-1)


def review_item(brain, obj, index, now):
    reasons = approval_blockers(brain, obj, index, now)
    state = obj["lifecycle"]
    current = eligible(obj["id"], index, now)
    if state in ("retired", "superseded"):
        next_action = "inactive"
    elif current:
        next_action = "none"
    elif state == "in-review":
        next_action = "resolve-blockers" if reasons else "human-review"
    elif state == "draft":
        next_action = "resolve-blockers" if reasons else "submit"
    else:
        next_action = "revise-and-resubmit"
    return {"id": obj["id"], "type": obj["type"], "title": obj["title"],
            "revision": obj["revision"], "lifecycle": state, "review_due_at": obj["review_due_at"],
            "current": current, "ready_for_approval": state == "in-review" and not reasons,
            "publication_blockers": reasons, "next_action": next_action,
            "dependency_depth": dependency_depth(obj["id"], index)}


def review_queue(brain):
    index = brain.contracts.graph(brain.store.all())
    now = brain.clock()
    items = [review_item(brain, obj, index, now) for obj in index.values()
             if obj["lifecycle"] not in ("retired", "superseded") and not eligible(obj["id"], index, now)]
    items.sort(key=lambda item: (item["dependency_depth"], not item["ready_for_approval"], item["id"]))
    return {"mode": "fixture" if brain.store.fixture_mode else "live", "as_of": now,
            "pending_count": len(items), "ready_for_approval": sum(i["ready_for_approval"] for i in items),
            "items": items, "note": "Read-only queue; ready means policy checks pass, not human approval."}


def review_packet(brain, object_id):
    index = brain.contracts.graph(brain.store.all())
    if object_id not in index:
        raise Invalid(f"Unknown object: {object_id}")
    now, upstream = brain.clock(), set()

    def visit(current_id):
        for target, _ in links(index[current_id]):
            if target not in upstream and target != object_id:
                upstream.add(target)
                visit(target)

    visit(object_id)
    ordered = sorted(upstream, key=lambda key: (dependency_depth(key, index), key))
    obj = index[object_id]
    return {"as_of": now, "summary": review_item(brain, obj, index, now), "object": obj,
            "dependencies": [{"object": index[key], "summary": review_item(brain, index[key], index, now)} for key in ordered],
            "conflicts": [{"object": c, "current": eligible(c["id"], index, now)} for c in index.values()
                          if c["type"] == "conflict" and object_id in c["claim_ids"]],
            "history": brain.store.history(object_id),
            "review_questions": ["Does the source support this bounded observation and interpretation?",
                                 "Are rights, attribution, applicability and source independence correctly declared?",
                                 "Are uncertainty, contrary evidence and normative versus informative status clear?",
                                 "Is the review date appropriate, and is this the exact revision you intend to approve?"],
            "note": "No review decision is recorded by this packet."}
