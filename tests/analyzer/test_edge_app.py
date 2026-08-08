"""까다로운 선언 방식을 모아 놓은 두 번째 픽스처에 대한 회귀 테스트.

여기 있는 항목은 전부 **실제로 틀렸던 것**들이다. 적대적 픽스처를 만들어
돌려 보고 나서야 드러났고, 다섯 개 모두 예외를 내지 않고 조용히 잘못된
값을 내던 종류였다.
"""

import pytest

from tests.conftest import EDGE_ROOT
from testweaver.analyzer.models import NoteCode, ParamLocation
from testweaver.analyzer.pipeline import analyze_project


@pytest.fixture(scope="module")
def result():
    return analyze_project(EDGE_ROOT)


@pytest.fixture(scope="module")
def features(result) -> dict:
    return {feature.id: feature for feature in result.features}


def constraint(feature, name):
    return next(c for c in feature.constraints if c.field_name == name)


# ─────────────── ① 모듈 상수 prefix ───────────────


def test_prefix_from_module_constant_is_resolved(features):
    """`API_PREFIX = "/api"` 를 못 읽으면 이 앱의 경로 11개가 전부 어긋난다."""
    assert "GET /api/secure/items/{sku}" in features
    assert not any(fid.startswith("GET /secure/") for fid in features)


def test_include_router_inside_app_factory_is_found(features):
    """create_app() 안에서 마운트해도 찾아야 한다."""
    assert "POST /api/secure/tree" in features


def test_nested_router_prefixes_accumulate(features):
    assert "GET /api/secure/nested/inner/leaf" in features


# ─────────────── ② 경로 변환기 ───────────────


def test_path_converter_is_stripped_from_the_url(features):
    """`{file_path:path}` 는 라우팅 규칙이지 URL 의 일부가 아니다."""
    assert "GET /api/secure/files/{file_path}" in features
    assert not any(":path" in fid for fid in features)


def test_converted_path_parameter_is_still_recognised(features):
    file_path = constraint(features["GET /api/secure/files/{file_path}"], "file_path")
    assert file_path.location is ParamLocation.PATH
    assert file_path.required is True


# ─────────────── ③ 헤더 이름 ───────────────


def test_header_underscores_become_hyphens(features):
    """FastAPI 는 Header 인자의 밑줄을 하이픈으로 바꿔 내보낸다.

    파이썬 이름을 그대로 쓰면 생성된 테스트가 엉뚱한 헤더를 보내 인증에
    실패한다.
    """
    header = constraint(features["GET /api/secure/nodes"], "x-api-key")
    assert header.location is ParamLocation.HEADER


def test_router_level_dependency_header_is_hoisted(features):
    """헤더는 라우터 단위 의존성 안에 있고 핸들러에는 나타나지 않는다."""
    for feature in features.values():
        names = {c.field_name for c in feature.constraints}
        assert "x-api-key" in names, feature.id
        assert "x_api_key" not in names


# ─────────────── ④ 호출 가능한 클래스 의존성 ───────────────


def test_callable_class_dependency_is_resolved(features):
    """`throttle = RateLimiter(10)` 은 함수가 아니라 변수다.

    클래스까지 되짚지 못하면 `__call__` 이 선언한 파라미터를 통째로 놓친다.
    """
    session = constraint(features["POST /api/secure/search"], "session")
    assert session.location is ParamLocation.COOKIE


def test_callable_class_dependency_is_not_reported_as_external(result):
    external = [
        note
        for note in result.notes
        if note.code is NoteCode.EXTERNAL_SYMBOL and "throttle" in note.message
    ]
    assert external == [], "프로젝트 안의 심볼을 밖이라고 잘못 알렸다"


# ─────────────── ⑤ 문자열 어노테이션 ───────────────


def test_forward_reference_annotation_is_followed(features):
    """`child: "Node | None"` 은 자기 자신을 품는 모델에 반드시 필요한 문법이다."""
    child = constraint(features["POST /api/secure/tree"], "root.child")
    assert child.type_name == "Node"
    assert child.nested_model.module == "schemas"
    assert child.nullable is True


# ─────────────── 나머지 선언 방식 ───────────────


def test_api_route_expands_into_one_feature_per_method(features):
    assert "GET /api/secure/multi" in features
    assert "POST /api/secure/multi" in features
    assert features["GET /api/secure/multi"].endpoint.success_status_code == 202


def test_stacked_method_decorators_produce_separate_features(features):
    assert "GET /api/secure/dual" in features
    assert "PUT /api/secure/dual" in features


def test_same_class_name_in_two_modules_is_disambiguated(features):
    """schemas.Item 과 other.Item 이 같은 이름이다."""
    model = features["POST /api/secure/barcode"].endpoint.request_model
    assert (model.name, model.module) == ("Item", "other")
    assert {c.field_name for c in features["POST /api/secure/barcode"].constraints} >= {
        "barcode",
        "weight",
    }


def test_router_level_dependency_marks_every_route_as_authenticated(features):
    assert all(f.endpoint.requires_auth for f in features.values()), (
        "APIRouter(dependencies=[...]) 로 건 인증"
    )


def test_optional_and_union_query_parameters(features):
    feature = features["POST /api/secure/search"]
    assert constraint(feature, "legacy").nullable is True
    assert constraint(feature, "mixed").nullable is True


def test_deprecated_flag_is_read(features):
    assert features["POST /api/secure/search"].endpoint.deprecated is True


# ─────────────── 정적으로 불가능한 것 ───────────────


def test_dynamic_route_is_reported_not_silently_dropped(result):
    """`add_api_route` 는 경로가 런타임 값이라 알아낼 수 없다.

    빠뜨리는 건 어쩔 수 없지만, 빠뜨렸다는 사실은 알려야 한다.
    """
    assert result.notes_with(NoteCode.DYNAMIC_ROUTE)
    assert not any(fid.endswith("/ping") for fid in {f.id for f in result.features})
