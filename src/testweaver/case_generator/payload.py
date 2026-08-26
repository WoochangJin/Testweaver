import re

from testweaver.analyzer.models import Constraint, ParamLocation

#: normal/boundary/security 케이스가 기대하는 "리소스가 존재함" id.
_EXISTING_ID = 1
#: 404(not-found) 계열 failure 케이스가 기대하는 "리소스가 존재하지 않음" id.
#: _EXISTING_ID와 절대 겹치지 않도록 임의로 큰 값을 사용 (#48).
_NOT_FOUND_ID = 99999


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


def build_path_params(path: str, *, not_found: bool = False) -> dict | None:
    """엔드포인트 경로에서 {name} 형태의 path param을 추출해 값을 채운다.

    기본값(not_found=False)은 리소스가 존재해야 하는 케이스(normal/boundary/
    security)용으로 _EXISTING_ID를 채운다. not_found=True는 404 같은
    not-found 계열 failure 케이스용으로, 같은 feature의 존재 케이스와
    id가 절대 겹치지 않도록 _NOT_FOUND_ID를 채운다 (#48 — 이전에는 항상
    같은 id(1)를 써서 exists 케이스와 not-found 케이스가 동시에 통과할
    수 없었음).
    """
    names = re.findall(r"\{(\w+)\}", path)
    value = _NOT_FOUND_ID if not_found else _EXISTING_ID
    return {name: value for name in names} or None