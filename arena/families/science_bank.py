"""Allowlisted scorer runtime; task generators and holdouts excluded."""
import json
import math
from typing import Any
TOLERANCE = 1e-5

def _unique_object(pairs):
    result = {}
    for key,value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result

def grade(task: dict, answer: Any) -> dict:
    """Bounded data-only grading. Scientific mismatches are graded zero.

    Accept a structured dict or its JSON encoding, and the shared {'value':str}
    envelope when value contains that JSON object. No candidate code is executed.
    """
    if isinstance(answer, dict) and set(answer) == {"value"}:
        answer = answer["value"]
    if isinstance(answer, str):
        if len(answer) > 8192:
            return {"status": "graded", "reward": 0.0, "checks": [{"id": "format", "passed": False}]}
        try:
            answer = json.loads(answer, object_pairs_hook=_unique_object,
                                parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
        except (ValueError, RecursionError):
            answer = None
    expected = task["expected"]
    if not isinstance(answer, dict) or set(answer) != set(expected):
        return {"status": "graded", "reward": 0.0, "checks": [{"id": "format", "passed": False}]}
    checks = []
    for field, reference in expected.items():
        value = answer[field]
        if isinstance(reference, str):
            passed = isinstance(value, str) and value == reference
        else:
            passed = (type(value) in (int, float) and abs(value) <= 1e100 and math.isfinite(value)
                      and (value == reference if type(reference) is int else abs(value - reference) <= TOLERANCE))
        checks.append({"id": field, "passed": bool(passed)})
    return {"status": "graded", "reward": float(all(c["passed"] for c in checks)), "checks": checks}
