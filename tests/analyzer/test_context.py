import pytest

from tests.conftest import FIXTURE_ROOT
from testweaver.analyzer.index.context import build_index
from testweaver.analyzer.models import SymbolRef


@pytest.fixture(scope="module")
def index():
    return build_index(FIXTURE_ROOT)


def _file(index, module_path: str):
    return next(m.path for m in index.modules.values() if m.module_path == module_path)


# ─────────────── 이름 해석 ───────────────


def test_resolves_imported_name_to_origin_module(index):
    ref = index.resolve(_file(index, "routers.auth"), "LoginRequest")
    assert (ref.name, ref.module) == ("LoginRequest", "schemas.auth")


def test_resolves_local_name_to_its_own_module(index):
    ref = index.resolve(_file(index, "deps"), "CurrentUser")
    assert (ref.name, ref.module) == ("CurrentUser", "deps")


# ─────────────── 크로스 파일 모델 조회 ───────────────


def test_finds_model_defined_in_another_file(index):
    """이 단계의 핵심. 핸들러가 있는 파일에는 모델 정의가 없다."""
    ref = index.resolve(_file(index, "routers.auth"), "LoginRequest")
    found = index.find_class(ref)
    assert found is not None
    assert found.module.module_path == "schemas.auth"


def test_pydantic_model_detected_through_inheritance(index):
    """SignupRequest → UserBase → BaseModel. 부모가 다른 파일에 있다."""
    ref = index.resolve(_file(index, "routers.auth"), "SignupRequest")
    assert index.is_pydantic_model(ref) is True


def test_plain_class_is_not_a_model(index):
    ref = index.resolve(_file(index, "deps"), "CurrentUser")
    assert index.is_pydantic_model(ref) is False


def test_unknown_symbol_is_not_a_model(index):
    assert index.is_pydantic_model(SymbolRef("Nonexistent", "nowhere")) is False


def test_mro_puts_child_before_parent(index):
    """제약 수집 시 자식의 재정의가 부모를 덮으려면 이 순서여야 한다."""
    ref = index.resolve(_file(index, "routers.auth"), "SignupRequest")
    assert [c.name for c in index.class_mro(ref)] == ["SignupRequest", "UserBase"]


def test_enum_values_are_reachable_across_files(index):
    ref = index.resolve(_file(index, "schemas.auth"), "Role")
    assert index.enum_values(ref) == ["admin", "user"]


def test_enum_values_none_for_non_enum(index):
    ref = index.resolve(_file(index, "schemas.auth"), "LoginRequest")
    assert index.enum_values(ref) is None


# ─────────────── 함수 · 호출 그래프 ───────────────


def test_finds_service_function_called_from_handler(index):
    """login 핸들러가 부르는 authenticate 는 다른 파일에 있다."""
    ref = index.resolve(_file(index, "routers.auth"), "authenticate")
    found = index.find_function(ref)
    assert found is not None
    assert found.module.module_path == "services.auth_service"


def test_third_party_symbol_is_not_in_project(index):
    ref = index.resolve(_file(index, "routers.auth"), "Depends")
    assert index.is_in_project(ref) is False


# ─────────────── 라우터 · 예외 ───────────────


def test_router_lookup_by_file_and_variable(index):
    router = index.router_for(_file(index, "routers.auth"), "router")
    assert router is not None
    assert router.full_prefix == "/api/v1/auth"


def test_custom_exception_maps_to_status_code(index):
    """errors.py 의 raise 와 main.py 의 핸들러가 같은 심볼로 이어진다."""
    ref = index.resolve(_file(index, "routers.orders"), "OrderNotFound")
    assert index.status_for_exception(ref) == 404


def test_unregistered_exception_has_no_status(index):
    assert index.status_for_exception(SymbolRef("ValueError", None)) is None


# ─────────────── 전체 ───────────────


def test_index_builds_without_errors(index):
    assert index.notes == [], f"예상치 못한 노트: {[str(n) for n in index.notes]}"


def test_index_is_deterministic():
    first = build_index(FIXTURE_ROOT)
    second = build_index(FIXTURE_ROOT)
    assert sorted(first.classes) == sorted(second.classes)
    assert sorted(first.functions) == sorted(second.functions)
