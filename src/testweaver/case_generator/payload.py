from testweaver.analyzer.models import Constraint


def _valid_value(constraint: Constraint):
    if constraint.pattern == "email":
        return "user@example.com"
    if constraint.min_length is not None:
        return "a" * max(constraint.min_length, 1)
    if constraint.ge is not None:
        return constraint.ge
    if constraint.le is not None:
        return constraint.le
    return "sample text"


def build_valid_payload(constraints: list[Constraint]) -> dict:
    return {c.field_name: _valid_value(c) for c in constraints}


def build_invalid_payload(constraints: list[Constraint], field_name: str, variant: str) -> dict:
    payload = build_valid_payload(constraints)
    if variant == "missing":
        payload.pop(field_name, None)
    elif variant == "below_min_length":
        payload[field_name] = "a"
    elif variant == "above_max_length":
        payload[field_name] = "a" * 1000
    elif variant == "pattern_mismatch":
        payload[field_name] = "invalid-format"
    elif variant == "below_ge":
        constraint = next(c for c in constraints if c.field_name == field_name)
        payload[field_name] = constraint.ge - 1
    elif variant == "above_le":
        constraint = next(c for c in constraints if c.field_name == field_name)
        payload[field_name] = constraint.le + 1
    return payload