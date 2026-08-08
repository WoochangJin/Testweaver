"""정적 분석 결과를 FastAPI 가 만든 OpenAPI 스펙과 대조한다.

보조 검증이다. 기능별 동작은 `test_extractors.py` 가 고정하고, 여기서는
"우리가 아직 모르는 걸 놓치고 있지 않은가"를 본다. 스펙에는 있는데 우리
출력에 없는 항목이 곧 미구현 목록이 된다.

프로덕션 경로는 대상 프로젝트를 실행하지 않는다. 앱을 로드하는 건 정답지가
필요한 이 파일뿐이다.

    uv run pytest -m parity          이 대조만
    uv run pytest -m "not parity"    나머지만
"""

import pytest

from tests.conftest import FIXTURE_ROOT
from tests.fixtures.sample_app.main import app
from testweaver.analyzer.pipeline import analyze_project

pytestmark = pytest.mark.parity

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


@pytest.fixture(scope="module")
def spec() -> dict:
    return app.openapi()


@pytest.fixture(scope="module")
def features() -> dict:
    result = analyze_project(FIXTURE_ROOT)
    return {(f.endpoint.path, f.endpoint.method.value): f for f in result.features}


def _operations(spec: dict):
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            if method.upper() in HTTP_METHODS:
                yield path, method.upper(), operation


def test_no_route_is_missing(spec, features):
    """경로 대조는 곧 prefix 합성 전체의 검증이다.

    OpenAPI 의 paths 키는 이미 prefix 가 합쳐진 완전 경로다.
    """
    declared = {(path, method) for path, method, _ in _operations(spec)}
    assert declared - set(features) == set()


def test_no_route_is_invented(spec, features):
    declared = {(path, method) for path, method, _ in _operations(spec)}
    assert set(features) - declared == set()


def test_no_parameter_is_missing(spec, features):
    """의존성 안에 선언된 헤더까지 포함해서 대조한다."""
    declared = {
        (path, method, parameter["name"], parameter["in"])
        for path, method, operation in _operations(spec)
        for parameter in operation.get("parameters", [])
    }
    extracted = {
        (path, method, constraint.field_name, constraint.location.value)
        for (path, method), feature in features.items()
        for constraint in feature.constraints
        if constraint.location.value in {"query", "path", "header", "cookie"}
    }
    assert declared - extracted == set()


def test_required_body_fields_match(spec, features):
    schemas = spec["components"]["schemas"]
    for feature in features.values():
        model = feature.endpoint.request_model
        if model is None or model.name not in schemas:
            continue
        declared = set(schemas[model.name].get("required", []))
        extracted = {
            constraint.field_name
            for constraint in feature.constraints
            if constraint.location.value == "body"
            and constraint.required
            and "." not in constraint.field_name
        }
        assert extracted == declared, model.name


def test_success_status_codes_match(spec, features):
    for path, method, operation in _operations(spec):
        successes = {
            int(code)
            for code in operation["responses"]
            if code.isdigit() and int(code) < 400
        }
        assert features[(path, method)].endpoint.success_status_code in successes


def test_body_constraints_match(spec, features):
    """minLength/maximum/pattern/enum 이 스펙과 같은 값인지."""
    schemas = spec["components"]["schemas"]
    keys = {
        "minLength": "min_length",
        "maxLength": "max_length",
        "minimum": "ge",
        "maximum": "le",
        "exclusiveMinimum": "gt",
        "exclusiveMaximum": "lt",
        "pattern": "pattern",
    }
    for feature in features.values():
        model = feature.endpoint.request_model
        if model is None or model.name not in schemas:
            continue
        properties = schemas[model.name]["properties"]
        for constraint in feature.constraints:
            if constraint.location.value != "body" or "." in constraint.field_name:
                continue
            declared = properties.get(constraint.field_name, {})
            for spec_key, our_key in keys.items():
                if spec_key in declared:
                    assert getattr(constraint, our_key) == declared[spec_key], (
                        f"{model.name}.{constraint.field_name}.{our_key}"
                    )
