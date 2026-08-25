from testweaver.analyzer.models import Constraint, ParamLocation
from testweaver.case_generator.payload import build_invalid_payload, build_valid_payload


def _constraints():
    return [
        Constraint(field_name="email", type_name="str", required=True, pattern="email"),
        Constraint(field_name="password", type_name="str", required=True, min_length=8),
        Constraint(field_name="age", type_name="int", required=True, ge=0, le=120),
        Constraint(field_name="role", type_name="str", required=True, allowed_values=["admin", "user", "guest"]),
    ]


def test_build_valid_payload_fills_every_field():
    payload = build_valid_payload(_constraints())
    assert set(payload.keys()) == {"email", "password", "age", "role"}


def test_build_valid_payload_email_pattern_uses_valid_email():
    payload = build_valid_payload(_constraints())
    assert payload["email"] == "user@example.com"


def test_build_valid_payload_min_length_meets_requirement():
    payload = build_valid_payload(_constraints())
    assert len(payload["password"]) >= 8


def test_build_valid_payload_numeric_range_uses_boundary_value():
    payload = build_valid_payload(_constraints())
    assert payload["age"] == 0


def test_build_invalid_payload_missing_removes_field():
    payload = build_invalid_payload(_constraints(), "email", "missing")
    assert "email" not in payload


def test_build_invalid_payload_below_min_length_breaks_length_rule():
    payload = build_invalid_payload(_constraints(), "password", "below_min_length")
    assert len(payload["password"]) < 8


def test_build_invalid_payload_pattern_mismatch_breaks_format():
    payload = build_invalid_payload(_constraints(), "email", "pattern_mismatch")
    assert payload["email"] == "invalid-format"


def test_build_invalid_payload_below_ge_breaks_lower_bound():
    payload = build_invalid_payload(_constraints(), "age", "below_ge")
    assert payload["age"] == -1


def test_build_invalid_payload_above_le_breaks_upper_bound():
    payload = build_invalid_payload(_constraints(), "age", "above_le")
    assert payload["age"] == 121


def test_build_invalid_payload_only_breaks_target_field():
    payload = build_invalid_payload(_constraints(), "password", "below_min_length")
    assert payload["email"] == "user@example.com"
    assert payload["age"] == 0


def test_build_valid_payload_allowed_values_uses_first_option():
    payload = build_valid_payload(_constraints())
    assert payload["role"] == "admin"
    assert payload["role"] in {"admin", "user", "guest"}


def test_build_invalid_payload_invalid_choice_breaks_allowed_values():
    payload = build_invalid_payload(_constraints(), "role", "invalid_choice")
    assert payload["role"] not in {"admin", "user", "guest"}


def test_build_invalid_payload_invalid_choice_only_breaks_target_field():
    payload = build_invalid_payload(_constraints(), "role", "invalid_choice")
    assert payload["email"] == "user@example.com"
    assert payload["age"] == 0


def test_build_valid_payload_ignores_non_body_constraints():
    constraints = [
        Constraint(field_name="user_id", type_name="int", location=ParamLocation.PATH),
        Constraint(field_name="limit", type_name="int", location=ParamLocation.QUERY, required=False),
        Constraint(field_name="authorization", type_name="str", location=ParamLocation.HEADER),
        Constraint(field_name="email", type_name="str", required=True, pattern="email"),
    ]
    payload = build_valid_payload(constraints)
    assert set(payload.keys()) == {"email"}


def test_build_invalid_payload_ignores_non_body_constraints():
    constraints = [
        Constraint(field_name="limit", type_name="int", location=ParamLocation.QUERY, required=False),
        Constraint(field_name="password", type_name="str", required=True, min_length=8),
    ]
    payload = build_invalid_payload(constraints, "password", "below_min_length")
    assert "limit" not in payload
    assert len(payload["password"]) < 8