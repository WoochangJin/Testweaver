import re

from testweaver.analyzer.models import Constraint, ParamLocation


def _valid_value(constraint: Constraint):
    if constraint.allowed_values:
        return constraint.allowed_values[0]
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
    body_only = [c for c in constraints if c.location is ParamLocation.BODY]
    return {c.field_name: _valid_value(c) for c in body_only}


def build_invalid_payload(constraints: list[Constraint], field_name: str, variant: str) -> dict:
    payload = build_valid_payload(constraints)
    if variant == "missing":
        payload.pop(field_name, None)
    elif variant == "below_min_length":
        constraint = next(c for c in constraints if c.field_name == field_name)
        payload[field_name] = "a" * max(constraint.min_length - 1, 0)
    elif variant == "above_max_length":
        constraint = next(c for c in constraints if c.field_name == field_name)
        payload[field_name] = "a" * (constraint.max_length + 1)
    elif variant == "pattern_mismatch":
        payload[field_name] = "invalid-format"
    elif variant == "below_ge":
        constraint = next(c for c in constraints if c.field_name == field_name)
        payload[field_name] = constraint.ge - 1
    elif variant == "above_le":
        constraint = next(c for c in constraints if c.field_name == field_name)
        payload[field_name] = constraint.le + 1
    elif variant == "invalid_choice":
        payload[field_name] = "__not_in_allowed_values__"
    return payload

def build_path_params(path: str) -> dict | None:
    names = re.findall(r"\{(\w+)\}", path)
    return {name: 1 for name in names} or None