"""직렬화 결과가 합의된 매트릭스 스키마를 만들 재료를 다 담고 있는지 확인한다.

매트릭스 스키마(합의본):

    [{ "feature_name", "endpoint", "method",
       "cases": [{ "id", "feature_name", "category", "description",
                   "expected_status", "expected_error_code",
                   "sample_payload", "source", "selected" }] }]

케이스를 만드는 건 analyzer 의 일이 아니다. 여기서는 케이스의 각 필드를
채울 재료가 실제로 나오는지만 확인한다.
"""

import json

import pytest

from tests.conftest import FIXTURE_ROOT
from testweaver.analyzer.pipeline import analyze_project
from testweaver.analyzer.serialize import analysis_to_dict, dumps, write_analysis


@pytest.fixture(scope="module")
def payload() -> dict:
    return analysis_to_dict(analyze_project(FIXTURE_ROOT))


@pytest.fixture(scope="module")
def by_id(payload) -> dict:
    return {feature["feature_id"]: feature for feature in payload["features"]}


# ─────────────── 매트릭스 상위 필드 ───────────────


def test_top_level_matrix_fields_are_present(by_id):
    """feature_name / endpoint / method 는 그대로 옮겨 담을 수 있어야 한다."""
    feature = by_id["POST /api/v1/auth/login"]
    assert feature["feature_name"] == "login"
    assert feature["endpoint"] == "/api/v1/auth/login"
    assert feature["method"] == "POST"


def test_feature_id_is_unique(payload):
    """핸들러 이름은 파일이 다르면 겹친다. 매트릭스가 케이스를 링크하려면
    유일한 식별자가 필요하다."""
    ids = [feature["feature_id"] for feature in payload["features"]]
    assert len(ids) == len(set(ids))


# ─────────────── cases[] 를 만들 재료 ───────────────


def test_normal_case_has_an_expected_status(by_id):
    assert by_id["POST /api/v1/auth/signup"]["success_status_code"] == 201
    assert by_id["DELETE /api/v1/orders/{order_id}"]["success_status_code"] == 204


def test_boundary_case_material_covers_every_location(payload):
    """경계 케이스는 제약에서 나온다. body 만이 아니라 path/query/header 도 있다."""
    locations = {
        constraint["location"]
        for feature in payload["features"]
        for constraint in feature["constraints"]
    }
    assert {"body", "path", "query", "header"} <= locations


def test_failure_case_material_carries_status_and_error_code(by_id):
    exceptions = by_id["POST /api/v1/auth/login"]["exceptions"]
    pairs = {(e["status_code"], e["error_code"]) for e in exceptions}
    assert (401, "INVALID_CREDENTIALS") in pairs
    assert (423, "ACCOUNT_LOCKED") in pairs


def test_security_case_material_distinguishes_401_from_403(by_id):
    protected = by_id["GET /api/v1/auth/me"]
    assert (protected["requires_auth"], protected["requires_permission"]) == (
        True,
        False,
    )

    admin_only = by_id["DELETE /api/v1/orders/{order_id}"]
    assert (admin_only["requires_auth"], admin_only["requires_permission"]) == (
        True,
        True,
    )


def test_unresolved_status_is_flagged_not_hidden(payload):
    """expected_status 가 null 이 될 때 그 이유를 알 수 있어야 한다."""
    for feature in payload["features"]:
        for exception in feature["exceptions"]:
            if exception["status_code"] is None:
                assert exception["resolved"] is False


# ─────────────── 값 표현 ───────────────


def test_constraint_keeps_location_and_bounds(by_id):
    constraints = {
        c["field_name"]: c for c in by_id["GET /api/v1/orders"]["constraints"]
    }
    assert constraints["q"]["location"] == "query"
    assert (constraints["q"]["min_length"], constraints["q"]["max_length"]) == (3, 50)
    assert constraints["sort"]["allowed_values"] == ["asc", "desc"]


def test_gt_and_lt_survive_serialisation(by_id):
    score = next(
        c
        for c in by_id["POST /api/v1/auth/signup"]["constraints"]
        if c["field_name"] == "score"
    )
    assert (score["gt"], score["lt"]) == (0, 100)
    assert "ge" not in score and "le" not in score


def test_symbols_keep_their_module(by_id):
    """이름만 남기면 코드 생성 단계에서 import 문을 만들 수 없다."""
    assert (
        by_id["POST /api/v1/auth/login"]["request_model"] == "schemas.auth.LoginRequest"
    )
    assert by_id["POST /api/v1/orders"]["dependencies"][0]["source"].startswith("deps.")


def test_paths_are_relative_to_the_project_root(payload):
    for feature in payload["features"]:
        source = feature["source_file"]
        assert not source.startswith("/"), source
        assert ":" not in source, "윈도우 절대 경로가 새어 나갔다"


# ─────────────── 형식 ───────────────


def test_output_is_valid_json_and_round_trips():
    result = analyze_project(FIXTURE_ROOT)
    assert json.loads(dumps(result)) == analysis_to_dict(result)


def test_write_analysis_creates_the_file(tmp_path):
    result = analyze_project(FIXTURE_ROOT)
    written = write_analysis(result, tmp_path / "out" / "analysis.json")
    assert json.loads(written.read_text(encoding="utf-8"))["features"]
