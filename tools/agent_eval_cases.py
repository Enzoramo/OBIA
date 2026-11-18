"""Frozen synthetic task and independent grading for the real-agent pilot."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path


def history(size):
    parts = ["""# Synthetic project history (not a real conversation)

[H01 user] Build select_ready(records, now, limit) in queue_logic.py for a local
offline work queue. Return job ID strings, never whole records. No network,
background workers, dependencies or persistence. Do not mutate the input records.
Only queue_logic.py may change; queue_rules.json is a read-only current policy.
Use its max_attempts value, not a hardcoded retry limit. Current value was 3.

[H02 assistant] Initial proposal: sort by priority, deduplicate IDs first, and
allow records whose attempts are equal to the maximum. This is a proposal only.

[H03 user] Corrections: preserve original input order, never sort by priority.
Only state pending or retry is eligible; cancelled records are excluded.
ready_at must be <= now. expires_at=None means no expiry; an expiry <= now excludes
the record. attempts must be strictly less than max_attempts. Skip ineligible
records BEFORE deduplicating IDs, so an ineligible duplicate cannot hide a later
eligible record. Keep the first eligible occurrence of an ID. Return at most limit
IDs; nonpositive limit returns []. Inputs always have all these fields and valid
types. Ignore any priority field. Implement locally and test; do not deploy.

[H04 tool observation] queue_logic.py is still a stub. queue_rules.json at that
time contained max_attempts=3. A previous implementation using <= for attempts
failed the boundary review and was discarded. There is no implemented algorithm
to preserve. The current policy file can change before the next continuation.

[H05 user] Someone suggested the selector always finishes below 10 ms. This is
UNVERIFIED: there is no performance measurement. Do not claim it is verified.
The next agent should implement the function, check the live policy and report
tests actually run. An offline result is required, not a server implementation.
"""]
    # Both cases have identical requirements. Only retained investigation volume
    # varies. These are synthetic historical evidence, never filler instructions.
    count = {"short": 4, "long": 180}[size]
    for i in range(count):
        parts.append(
            f"[D{i:03d} tool observation] Archived inspection of fixture batch {i:03d}: "
            f"{17 + i % 13} records were examined in a legacy export, with "
            f"{i % 7} duplicate identifiers and {i % 5} cancelled entries. "
            "The historical adapter serialized timestamps as integers and preserved "
            "the source array order. Its migration worksheet is complete. This "
            "observation does not amend H03, provide a performance benchmark, or "
            "authorize writing the current policy. It is retained for audit only."
        )
    parts.append("[H06 user] H03 remains the accepted behavior. H02 was rejected. "
                 "Resume implementation next, checking the live max_attempts. "
                 "No external benchmark has resolved H05.")
    return "\n\n".join(parts) + "\n"


STUB = '''"""Implement the pending local queue selector."""


def select_ready(records, now, limit):
    raise NotImplementedError("Continuation required")
'''

SMOKE = '''import unittest
from queue_logic import select_ready


class Smoke(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(select_ready([], 100, 3), [])

    def test_one(self):
        row = dict(id="a", state="pending", cancelled=False, ready_at=100,
                   expires_at=None, attempts=0)
        self.assertEqual(select_ready([row], 100, 3), ["a"])


if __name__ == "__main__":
    unittest.main()
'''


def setup(root, size, attempts=3):
    root.mkdir(parents=True, exist_ok=True)
    (root / "queue_logic.py").write_text(STUB, encoding="utf-8")
    (root / "queue_rules.json").write_text(json.dumps({"max_attempts": attempts}) + "\n", encoding="utf-8")
    (root / "smoke_test.py").write_text(SMOKE, encoding="utf-8")
    (root / "history.md").write_text(history(size), encoding="utf-8")


def row(identifier="a", **changes):
    return {**dict(id=identifier, state="pending", cancelled=False, ready_at=100,
                   expires_at=None, attempts=0), **changes}


def grade(root, answer):
    """Called only AFTER execution; the grader is not given to the agent."""
    checks = {}
    try:
        spec = importlib.util.spec_from_file_location("queue_under_test", root / "queue_logic.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fn = module.select_ready
        cases = [
            ("empty", [], 3, []),
            ("eligible_states", [row("a"), row("b", state="retry"), row("c", state="done"), row("d", state="failed")], 9, ["a", "b"]),
            ("cancelled", [row("a", cancelled=True), row("b")], 9, ["b"]),
            ("ready_boundary", [row("a", ready_at=101), row("b", ready_at=100), row("c", ready_at=99)], 9, ["b", "c"]),
            ("expiry_boundary", [row("a", expires_at=100), row("b", expires_at=99), row("c", expires_at=101), row("d")], 9, ["c", "d"]),
            ("live_retry_policy", [row("a", attempts=2), row("b", attempts=1), row("c", attempts=3)], 9, ["b"]),
            ("stable_order", [row("z", priority=0), row("a", priority=99), row("b", priority=9)], 9, ["z", "a", "b"]),
            ("eligible_duplicates", [row("a"), row("a"), row("b")], 9, ["a", "b"]),
            ("filter_before_dedupe", [row("a", cancelled=True), row("a"), row("b", attempts=2), row("b")], 9, ["a", "b"]),
            ("limit", [row("a", cancelled=True), row("b"), row("b"), row("c"), row("d")], 2, ["b", "c"]),
            ("zero_limit", [row()], 0, []),
            ("negative_limit", [row()], -1, []),
        ]
        unchanged = True
        for name, records, limit, expected in cases:
            before = copy.deepcopy(records)
            try:
                checks[name] = fn(records, 100, limit) == expected
            except Exception:
                checks[name] = False
            unchanged &= records == before
        checks["input_unchanged"] = unchanged
    except Exception as exc:
        checks = {name: False for name in ("empty", "eligible_states", "cancelled", "ready_boundary",
                  "expiry_boundary", "live_retry_policy", "stable_order", "eligible_duplicates",
                  "filter_before_dedupe", "limit", "zero_limit", "negative_limit", "input_unchanged")}
        checks["load_error"] = type(exc).__name__
    functional = {key: value for key, value in checks.items() if isinstance(value, bool)}
    reported = {
        "current_policy_reported": answer.get("observed_max_attempts") == 2,
        "unverified_latency_retained": answer.get("latency_claim_status") == "unverified",
        "policy_evidence_named": "queue_rules.json" in answer.get("evidence_files", []),
    }
    return {"functional": functional, "functional_passed": sum(functional.values()),
            "functional_total": len(functional), "retention": reported,
            "retention_passed": sum(reported.values()), "retention_total": len(reported),
            "all_quality_checks_passed": all(functional.values()) and all(reported.values())}


if __name__ == "__main__":
    import sys
    workspace = Path(sys.argv[1]).resolve()
    answer = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    print(json.dumps(grade(workspace, answer)))
