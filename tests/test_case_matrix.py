from testweaver.analyzer.models import (
    Constraint,
    Endpoint,
    ExceptionFlow,
    Feature,
    HttpMethod,
)
from testweaver.case_generator.rules import (
    derive_boundary_cases,
    derive_failure_cases,
    derive_normal_cases,
    derive_security_cases,
)


def _mock_feature(**overrides) -> Feature:
    endpoint = Endpoint(
        path=overrides.get("path", "/users"),
        method=HttpMethod.POST,
        handler_name="register",
        requires_auth=overrides.get("requires_auth", False),
        exceptions=overrides.get("exceptions", []),
    )
    return Feature(
        id=f"{endpoint.method.value} {endpoint.path}",
        name="register",
        endpoint=endpoint,
        constraints=overrides.get("constraints", []),
    )


def test_derive_normal_cases_returns_one_case():
    feature = _mock_feature()
    cases = derive_normal_cases(feature)
    assert len(cases) == 1
    assert cases[0].expected_status == 200


def test_derive_normal_cases_extracts_path_params():
    feature = _mock_feature(path="/users/{user_id}")
    cases = derive_normal_cases(feature)
    assert cases[0].path_params == {"user_id": 1}


def test_derive_boundary_cases_covers_each_constraint_rule():
    feature = _mock_feature(
        constraints=[
            Constraint(field_name="email", type_name="str", required=True, pattern="email"),
            Constraint(field_name="password", type_name="str", required=True, min_length=8),
        ]
    )
    cases = derive_boundary_cases(feature)
    assert len(cases) == 4
    assert all(case.expected_status == 422 for case in cases)


def test_derive_failure_cases_maps_each_exception():
    feature = _mock_feature(
        exceptions=[ExceptionFlow(exception_type="HTTPException", status_code=400, error_code="dup_email")]
    )
    cases = derive_failure_cases(feature)
    assert len(cases) == 1
    assert cases[0].expected_status == 400
    assert cases[0].expected_error_code == "dup_email"


def test_derive_security_cases_only_when_auth_required():
    assert derive_security_cases(_mock_feature(requires_auth=False)) == []

    cases = derive_security_cases(_mock_feature(requires_auth=True))
    assert len(cases) == 1
    assert cases[0].expected_status == 401

def test_normal_case_status_resolved():
    endpoint = Endpoint(
        path="/users",
        method=HttpMethod.DELETE,
        handler_name="delete_user",
        success_status_code=204,
    )
    feature = Feature(id="DELETE /users", name="delete_user", endpoint=endpoint, constraints=[])

    cases = derive_normal_cases(feature)

    assert cases[0].expected_status == 204


def test_normal_case_status_unresolved():
    endpoint = Endpoint(
        path="/users",
        method=HttpMethod.POST,
        handler_name="create_user",
        success_status_code=None,  # status_code 인자는 있는데 해석 실패한 상황
    )
    feature = Feature(id="POST /users", name="create_user", endpoint=endpoint, constraints=[])

    cases = derive_normal_cases(feature)

    assert cases[0].expected_status is None