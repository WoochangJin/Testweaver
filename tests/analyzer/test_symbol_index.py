import pytest

from tests.conftest import FIXTURE_ROOT
from testweaver.analyzer.index.file_index import collect_modules
from testweaver.analyzer.index.symbol_index import index_classes, index_functions


@pytest.fixture(scope="module")
def modules() -> dict:
    return collect_modules(FIXTURE_ROOT)


def test_classes_are_indexed_by_qualified_name(modules):
    by_qualified, _ = index_classes(modules)
    assert "schemas.auth.LoginRequest" in by_qualified
    assert "schemas.base.UserBase" in by_qualified
    assert "schemas.order.OrderItem" in by_qualified


def test_base_names_are_recorded_without_judging(modules):
    """상속 판정은 미루고 이름만 적어 둔다."""
    by_qualified, _ = index_classes(modules)
    assert by_qualified["schemas.auth.SignupRequest"].base_names == ["UserBase"]
    assert by_qualified["schemas.auth.LoginRequest"].base_names == ["BaseModel"]


def test_enum_values_are_collected(modules):
    """멤버 이름이 아니라 값을 담는다. 요청에 실려 가는 건 값이다."""
    by_qualified, _ = index_classes(modules)
    role = by_qualified["schemas.auth.Role"]
    assert role.is_enum is True
    assert role.enum_values == ["admin", "user"]


def test_non_enum_class_has_no_values(modules):
    by_qualified, _ = index_classes(modules)
    login = by_qualified["schemas.auth.LoginRequest"]
    assert login.is_enum is False
    assert login.enum_values is None


def test_plain_class_is_indexed_too(modules):
    """Pydantic 모델만 걸러 담지 않는다. 판정은 Pass 2 의 일이다."""
    by_qualified, _ = index_classes(modules)
    assert "deps.CurrentUser" in by_qualified


def test_name_index_keeps_all_candidates(modules):
    _, by_name = index_classes(modules)
    assert [c.qualified_name for c in by_name["UserBase"]] == ["schemas.base.UserBase"]


def test_top_level_functions_are_indexed(modules):
    by_qualified, _ = index_functions(modules)
    assert "services.auth_service.authenticate" in by_qualified
    assert "deps.get_current_user" in by_qualified
    assert "routers.auth.login" in by_qualified


def test_route_handlers_are_functions_too(modules):
    """핸들러도 최상위 함수라 같은 색인에 들어간다."""
    by_qualified, _ = index_functions(modules)
    assert by_qualified["routers.orders.get_order"].name == "get_order"
