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

from tests.conftest import (
    ALIAS_ROOT,
    EDGE_ROOT,
    FIXTURE_ROOT,
    FLOW_ROOT,
    VARIANT_ROOT,
)
from tests.fixtures.alias_app.main import app as alias_app
from tests.fixtures.edge_app.main import app as edge_app
from tests.fixtures.flow_app.main import app as flow_app
from tests.fixtures.sample_app.main import app as sample_app
from tests.fixtures.variant_app.main import app as variant_app
from testweaver.analyzer.pipeline import analyze_project

pytestmark = pytest.mark.parity

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


#: (앱, 분석 루트) 쌍. 두 픽스처를 같은 대조에 건다.
APPS = [
    pytest.param(sample_app, FIXTURE_ROOT, id="sample"),
    pytest.param(edge_app, EDGE_ROOT, id="edge"),
    pytest.param(variant_app, VARIANT_ROOT, id="variant"),
    pytest.param(flow_app, FLOW_ROOT, id="flow"),
    pytest.param(alias_app, ALIAS_ROOT, id="alias"),
]

#: 정적 분석으로는 경로를 알 수 없어 대조에서 빼는 라우트.
#: `add_api_route` 는 인자가 런타임 값이다. 빠뜨리되 노트로 알린다.
UNREACHABLE = {("/ping", "GET")}


def _features(root) -> dict:
    result = analyze_project(root)
    return {(f.endpoint.path, f.endpoint.method.value): f for f in result.features}


def _operations(spec: dict):
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            if method.upper() in HTTP_METHODS:
                yield path, method.upper(), operation


@pytest.mark.parametrize(("app", "root"), APPS)
def test_no_route_is_missing(app, root):
    spec, features = app.openapi(), _features(root)
    """경로 대조는 곧 prefix 합성 전체의 검증이다.

    OpenAPI 의 paths 키는 이미 prefix 가 합쳐진 완전 경로다.
    """
    declared = {(path, method) for path, method, _ in _operations(spec)} - UNREACHABLE
    assert declared - set(features) == set()


@pytest.mark.parametrize(("app", "root"), APPS)
def test_no_route_is_invented(app, root):
    spec, features = app.openapi(), _features(root)
    declared = {(path, method) for path, method, _ in _operations(spec)}
    assert set(features) - declared == set()


@pytest.mark.parametrize(("app", "root"), APPS)
def test_no_parameter_is_missing(app, root):
    spec, features = app.openapi(), _features(root)
    """의존성 안에 선언된 헤더까지 포함해서 대조한다."""
    declared = {
        (path, method, parameter["name"], parameter["in"])
        for path, method, operation in _operations(spec)
        for parameter in operation.get("parameters", [])
        if (path, method) not in UNREACHABLE
    }
    extracted = {
        (path, method, constraint.field_name, constraint.location.value)
        for (path, method), feature in features.items()
        for constraint in feature.constraints
        if constraint.location.value in {"query", "path", "header", "cookie"}
    }
    assert declared - extracted == set()


@pytest.mark.parametrize(("app", "root"), APPS)
def test_required_body_fields_match(app, root):
    spec, features = app.openapi(), _features(root)
    # 본문이 하나도 없는 앱에는 components 자체가 없다.
    schemas = spec.get("components", {}).get("schemas", {})
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


@pytest.mark.parametrize(("app", "root"), APPS)
def test_success_status_codes_match(app, root):
    spec, features = app.openapi(), _features(root)
    for path, method, operation in _operations(spec):
        if (path, method) in UNREACHABLE:
            continue
        successes = {
            int(code)
            for code in operation["responses"]
            if code.isdigit() and int(code) < 400
        }
        assert features[(path, method)].endpoint.success_status_code in successes


@pytest.mark.parametrize(("app", "root"), APPS)
def test_body_constraints_match(app, root):
    spec, features = app.openapi(), _features(root)
    """minLength/maximum/pattern/enum 이 스펙과 같은 값인지."""
    # 본문이 하나도 없는 앱에는 components 자체가 없다.
    schemas = spec.get("components", {}).get("schemas", {})
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
