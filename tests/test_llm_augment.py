import json

import pytest

from testweaver.analyzer.models import Endpoint, Feature, HttpMethod
from testweaver.llm_augment import augment_matrices, augment_matrix, get_llm_client
from testweaver.schema import CaseCategory, CaseSource
from testweaver.schema import TestCase as SchemaTestCase
from testweaver.schema import TestCaseMatrix as SchemaTestCaseMatrix


def _mock_feature(**overrides) -> Feature:
    endpoint = Endpoint(
        path=overrides.get("path", "/users"),
        method=HttpMethod.POST,
        handler_name="register",
    )
    return Feature(
        id=f"{endpoint.method.value} {endpoint.path}",
        name="register",
        endpoint=endpoint,
        constraints=overrides.get("constraints", []),
    )


def _rule_case(case_id: str) -> SchemaTestCase:
    return SchemaTestCase(
        id=case_id,
        feature_name="register",
        category=CaseCategory.NORMAL,
        description="rule-derived case",
        source=CaseSource.RULE,
    )


class _FakeCompletions:
    def __init__(self, response_body: dict):
        self._response_body = response_body
        self.last_request = None

    def create(self, **kwargs):
        self.last_request = kwargs
        message = type("Message", (), {"content": json.dumps(self._response_body)})
        choice = type("Choice", (), {"message": message})
        return type("Response", (), {"choices": [choice()]})()


class _FakeChat:
    def __init__(self, response_body: dict):
        self.completions = _FakeCompletions(response_body)


class _FakeClient:
    def __init__(self, response_body: dict):
        self.chat = _FakeChat(response_body)


def test_get_llm_client_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert get_llm_client() is None


def test_augment_matrices_passes_through_unchanged_when_client_is_none():
    matrix = SchemaTestCaseMatrix(
        feature_name="register", endpoint="/users", method="POST", cases=[_rule_case("register-1")]
    )
    result = augment_matrices([matrix], [_mock_feature()], client=None)
    assert result == [matrix]


def test_augment_matrix_ranks_rule_cases_and_appends_llm_cases():
    matrix = SchemaTestCaseMatrix(
        feature_name="register",
        endpoint="/users",
        method="POST",
        cases=[_rule_case("register-1"), _rule_case("register-2")],
    )
    client = _FakeClient(
        {
            "new_cases": [
                {
                    "temp_id": "llm-a",
                    "category": "security",
                    "description": "SQL injection in email field",
                    "expected_status": 422,
                    "expected_error_code": None,
                    "sample_payload": None,
                    "path_params": None,
                }
            ],
            "priority_order": ["llm-a", "register-1", "register-2"],
        }
    )

    updated = augment_matrix(matrix, _mock_feature(), client)

    by_id = {case.id: case for case in updated.cases}
    assert len(updated.cases) == 3
    assert by_id["register-llm-1"].source is CaseSource.LLM
    assert by_id["register-llm-1"].category is CaseCategory.SECURITY
    assert by_id["register-llm-1"].priority == 1
    assert by_id["register-1"].priority == 2
    assert by_id["register-2"].priority == 3


def test_augment_matrix_rejects_priority_order_missing_a_case():
    matrix = SchemaTestCaseMatrix(
        feature_name="register",
        endpoint="/users",
        method="POST",
        cases=[_rule_case("register-1"), _rule_case("register-2")],
    )
    client = _FakeClient({"new_cases": [], "priority_order": ["register-1"]})

    with pytest.raises(ValueError, match="does not match the case set"):
        augment_matrix(matrix, _mock_feature(), client)


def test_augment_matrix_rejects_priority_order_with_duplicates():
    matrix = SchemaTestCaseMatrix(
        feature_name="register", endpoint="/users", method="POST", cases=[_rule_case("register-1")]
    )
    client = _FakeClient({"new_cases": [], "priority_order": ["register-1", "register-1"]})

    with pytest.raises(ValueError, match="duplicate ids"):
        augment_matrix(matrix, _mock_feature(), client)


def test_augment_matrix_rejects_new_case_temp_id_colliding_with_existing_case_id():
    matrix = SchemaTestCaseMatrix(
        feature_name="register",
        endpoint="/users",
        method="POST",
        cases=[_rule_case("register-1"), _rule_case("register-2")],
    )
    client = _FakeClient(
        {
            "new_cases": [
                {
                    "temp_id": "register-1",  # collides with an existing rule case id
                    "category": "security",
                    "description": "duplicate id case",
                    "expected_status": None,
                    "expected_error_code": None,
                    "sample_payload": None,
                    "path_params": None,
                }
            ],
            "priority_order": ["register-1", "register-2"],
        }
    )

    with pytest.raises(ValueError, match="collide with existing case ids"):
        augment_matrix(matrix, _mock_feature(), client)


def test_augment_matrix_rejects_duplicate_temp_ids_among_new_cases():
    matrix = SchemaTestCaseMatrix(
        feature_name="register", endpoint="/users", method="POST", cases=[_rule_case("register-1")]
    )
    new_case_spec = {
        "temp_id": "llm-a",
        "category": "security",
        "description": "dup temp id",
        "expected_status": None,
        "expected_error_code": None,
        "sample_payload": None,
        "path_params": None,
    }
    client = _FakeClient(
        {
            "new_cases": [new_case_spec, new_case_spec],
            "priority_order": ["register-1", "llm-a"],
        }
    )

    with pytest.raises(ValueError, match="duplicate temp_ids"):
        augment_matrix(matrix, _mock_feature(), client)


def test_augment_matrix_rejects_null_byte_in_description():
    matrix = SchemaTestCaseMatrix(
        feature_name="register", endpoint="/users", method="POST", cases=[_rule_case("register-1")]
    )
    client = _FakeClient(
        {
            "new_cases": [
                {
                    "temp_id": "llm-a",
                    "category": "security",
                    "description": "email \x00\x00 invalid",
                    "expected_status": None,
                    "expected_error_code": None,
                    "sample_payload": None,
                    "path_params": None,
                }
            ],
            "priority_order": ["register-1", "llm-a"],
        }
    )

    with pytest.raises(ValueError, match="garbled"):
        augment_matrix(matrix, _mock_feature(), client)


def test_augment_matrix_rejects_replacement_char_in_expected_error_code():
    matrix = SchemaTestCaseMatrix(
        feature_name="register", endpoint="/users", method="POST", cases=[_rule_case("register-1")]
    )
    client = _FakeClient(
        {
            "new_cases": [
                {
                    "temp_id": "llm-a",
                    "category": "security",
                    "description": "malformed token",
                    "expected_status": 400,
                    "expected_error_code": "INVALID_�TOKEN",
                    "sample_payload": None,
                    "path_params": None,
                }
            ],
            "priority_order": ["register-1", "llm-a"],
        }
    )

    with pytest.raises(ValueError, match="garbled"):
        augment_matrix(matrix, _mock_feature(), client)


def test_augment_matrix_does_not_mutate_original_matrix():
    matrix = SchemaTestCaseMatrix(
        feature_name="register", endpoint="/users", method="POST", cases=[_rule_case("register-1")]
    )
    client = _FakeClient({"new_cases": [], "priority_order": ["register-1"]})

    augment_matrix(matrix, _mock_feature(), client)

    assert matrix.cases[0].priority is None
