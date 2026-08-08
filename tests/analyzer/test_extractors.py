import pytest

from tests.conftest import FIXTURE_ROOT
from testweaver.analyzer.extractors import DEFAULT_EXTRACTORS, order_extractors
from testweaver.analyzer.models import NoteCode, ParamLocation
from testweaver.analyzer.pipeline import analyze_project


@pytest.fixture(scope="module")
def features() -> dict:
    result = analyze_project(FIXTURE_ROOT)
    return {feature.id: feature for feature in result.features}


@pytest.fixture(scope="module")
def result():
    return analyze_project(FIXTURE_ROOT)


def constraint(feature, name):
    return next(c for c in feature.constraints if c.field_name == name)


# ─────────────────── 실행 순서 ───────────────────


def test_extractors_run_in_dependency_order():
    order = [extractor.name for extractor in order_extractors(list(DEFAULT_EXTRACTORS))]
    assert order.index("route") < order.index("params")
    assert order.index("params") < order.index("body")
    assert order.index("dependency") < order.index("auth")
    assert order.index("dependency") < order.index("exception")


# ─────────────────── route ───────────────────


def test_path_is_fully_composed(features):
    assert "POST /api/v1/auth/login" in features
    assert "GET /health" in features, "라우터 없이 app 에 직접 붙은 것도 잡아야 한다"


def test_declared_status_code_is_used_not_assumed(features):
    assert features["POST /api/v1/auth/signup"].endpoint.success_status_code == 201
    assert (
        features["DELETE /api/v1/orders/{order_id}"].endpoint.success_status_code == 204
    )
    assert features["GET /api/v1/auth/me"].endpoint.success_status_code == 200


def test_response_model_resolves_across_files(features):
    model = features["POST /api/v1/auth/login"].endpoint.response_model
    assert (model.name, model.module) == ("TokenResponse", "schemas.auth")


def test_response_model_unwraps_containers(features):
    """response_model=list[OrderOut] 의 안쪽 모델을 가리킨다."""
    model = features["GET /api/v1/orders"].endpoint.response_model
    assert model.name == "OrderOut"


def test_tags_are_inherited_from_router(features):
    assert features["POST /api/v1/auth/login"].endpoint.tags == ["auth"]


def test_source_location_is_recorded(features):
    endpoint = features["POST /api/v1/auth/login"].endpoint
    assert endpoint.module_path == "routers.auth"
    assert endpoint.source_file is not None


# ─────────────────── params ───────────────────


def test_path_parameter_is_located_and_required(features):
    order_id = constraint(features["GET /api/v1/orders/{order_id}"], "order_id")
    assert order_id.location is ParamLocation.PATH
    assert order_id.required is True
    assert order_id.ge == 1


def test_query_parameters_keep_their_constraints(features):
    feature = features["GET /api/v1/orders"]
    q = constraint(feature, "q")
    assert (q.location, q.required) == (ParamLocation.QUERY, False)
    assert (q.min_length, q.max_length) == (3, 50)

    limit = constraint(feature, "limit")
    assert (limit.ge, limit.le, limit.default) == (1, 100, 20)


def test_bare_scalar_defaults_to_query(features):
    """마커 없는 스칼라는 쿼리 파라미터라는 FastAPI 규칙."""
    sort = constraint(features["GET /api/v1/orders"], "sort")
    assert sort.location is ParamLocation.QUERY
    assert sort.allowed_values == ["asc", "desc"]
    assert sort.required is False


def test_dependency_arguments_are_not_treated_as_parameters(features):
    names = {c.field_name for c in features["GET /api/v1/orders"].constraints}
    assert "user" not in names, "Annotated[..., Depends()] 는 입력이 아니다"


# ─────────────────── body ───────────────────


def test_required_follows_default_presence_not_type(features):
    """Field(min_length=8) 은 기본값이 없으므로 필수다.

    이걸 선택으로 보면 '필드 누락' 경계 케이스가 한 건도 안 생긴다.
    """
    feature = features["POST /api/v1/auth/signup"]
    required = {c.field_name for c in feature.constraints if c.required}
    assert required == {"nickname", "email", "password", "role"}


def test_inherited_field_is_collected(features):
    """nickname 은 UserBase 에 있고 UserBase 는 다른 파일에 있다."""
    nickname = constraint(features["POST /api/v1/auth/signup"], "nickname")
    assert (nickname.min_length, nickname.max_length) == (2, 20)


def test_gt_and_lt_are_not_collapsed_into_ge_le(features):
    """OpenAPI 도 exclusiveMinimum 과 minimum 을 구분한다."""
    score = constraint(features["POST /api/v1/auth/signup"], "score")
    assert (score.gt, score.lt) == (0, 100)
    assert (score.ge, score.le) == (None, None)


def test_enum_and_literal_become_allowed_values(features):
    feature = features["POST /api/v1/auth/signup"]
    assert constraint(feature, "role").allowed_values == ["admin", "user"]
    assert constraint(feature, "status").allowed_values == ["active", "banned"]


def test_default_factory_is_recorded_as_optional(features):
    tags = constraint(features["POST /api/v1/auth/signup"], "tags")
    assert tags.required is False
    assert tags.default_factory == "list"


def test_model_config_is_not_a_field(features):
    names = {c.field_name for c in features["POST /api/v1/auth/signup"].constraints}
    assert "model_config" not in names


def test_custom_validator_is_flagged(features):
    password = constraint(features["POST /api/v1/auth/signup"], "password")
    assert password.has_custom_validator is True


def test_nested_model_is_expanded_with_correct_module(features):
    """중첩 모델의 모듈이 핸들러 파일이 아니라 선언 파일이어야 한다."""
    feature = features["POST /api/v1/orders"]
    items = constraint(feature, "items")
    assert items.nested_model.module == "schemas.order"

    inner = constraint(feature, "items.product_id")
    assert inner.ge == 1
    assert inner.location is ParamLocation.BODY


# ─────────────────── dependency · auth ───────────────────


def test_annotated_dependency_is_detected(features):
    """기본값이 없는 문법이라 인자 기본값만 뒤지면 통째로 놓친다."""
    sources = {
        str(d.source) for d in features["GET /api/v1/auth/me"].endpoint.dependencies
    }
    assert "deps.get_current_user" in sources


def test_decorator_level_dependency_is_collected(features):
    """@router.delete(..., dependencies=[Depends(require_admin)])"""
    endpoint = features["DELETE /api/v1/orders/{order_id}"].endpoint
    assert "deps.require_admin" in {str(d.source) for d in endpoint.dependencies}


def test_transitive_dependency_is_followed(features):
    """require_admin 이 다시 get_current_user 에 의존한다."""
    endpoint = features["DELETE /api/v1/orders/{order_id}"].endpoint
    assert "deps.get_current_user" in {str(d.source) for d in endpoint.dependencies}


def test_auth_and_permission_are_distinguished(features):
    protected = features["GET /api/v1/auth/me"].endpoint
    assert (protected.requires_auth, protected.requires_permission) == (True, False)

    admin_only = features["DELETE /api/v1/orders/{order_id}"].endpoint
    assert (admin_only.requires_auth, admin_only.requires_permission) == (True, True)

    public = features["GET /health"].endpoint
    assert public.requires_auth is False


def test_non_auth_dependency_is_not_flagged(features):
    """get_db 는 인증과 무관하다."""
    endpoint = features["GET /api/v1/orders/{order_id}"].endpoint
    assert endpoint.requires_auth is False
    assert {str(d.source) for d in endpoint.dependencies} == {"deps.get_db"}


# ─────────────────── exception ───────────────────


def test_exceptions_from_service_layer_are_found(features):
    """login 핸들러에는 raise 가 하나도 없다. authenticate 안에 있다."""
    endpoint = features["POST /api/v1/auth/login"].endpoint
    found = {(e.status_code, e.error_code) for e in endpoint.exceptions}
    assert (401, "INVALID_CREDENTIALS") in found
    assert (423, "ACCOUNT_LOCKED") in found
    assert all(e.depth > 0 for e in endpoint.exceptions), "핸들러 본문 밖에서 왔다"


def test_status_constant_is_resolved(features):
    """status.HTTP_423_LOCKED 는 literal_eval 로는 해석되지 않는다."""
    endpoint = features["POST /api/v1/auth/login"].endpoint
    assert all(e.resolved for e in endpoint.exceptions)


def test_custom_exception_uses_global_handler_status(features):
    """raise 는 routers/orders.py, 핸들러는 main.py 에 있다."""
    endpoint = features["GET /api/v1/orders/{order_id}"].endpoint
    custom = next(e for e in endpoint.exceptions if e.exception_type == "OrderNotFound")
    assert custom.status_code == 404
    assert custom.resolved is True


def test_dependency_exceptions_are_attributed_to_the_endpoint(features):
    """get_current_user 의 401 은 핸들러 어디에도 안 보인다."""
    endpoint = features["GET /api/v1/auth/me"].endpoint
    assert 401 in {e.status_code for e in endpoint.exceptions}


# ─────────────────── effects ───────────────────


def test_no_unexpected_analysis_failures(result):
    unexpected = [n for n in result.notes if n.code is not NoteCode.CUSTOM_VALIDATOR]
    assert unexpected == [], [str(n) for n in unexpected]


def test_custom_validator_note_is_reported(result):
    assert result.notes_with(NoteCode.CUSTOM_VALIDATOR), "표현 못 한 제약은 알려야 한다"
