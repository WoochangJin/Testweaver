import ast
from pathlib import Path

import pytest

from tests.conftest import FIXTURE_ROOT
from testweaver.analyzer.index.file_index import ModuleInfo, collect_modules
from testweaver.analyzer.index.import_map import build_import_map


@pytest.fixture(scope="module")
def maps() -> dict:
    modules = collect_modules(FIXTURE_ROOT)
    return {m.module_path: build_import_map(m) for m in modules.values()}


def _module(source: str, module_path: str, is_package: bool = False) -> ModuleInfo:
    return ModuleInfo(
        path=Path("x.py"),
        module_path=module_path,
        tree=ast.parse(source),
        is_package=is_package,
    )


def test_absolute_from_import(maps):
    ref = maps["routers.auth"].resolve("LoginRequest")
    assert (ref.name, ref.module) == ("LoginRequest", "schemas.auth")


def test_relative_import_one_level(maps):
    """schemas/auth.py 의 `from .base import UserBase`."""
    ref = maps["schemas.auth"].resolve("UserBase")
    assert (ref.name, ref.module) == ("UserBase", "schemas.base")


def test_relative_import_two_levels(maps):
    """routers/auth.py 의 `from ..deps import CurrentUser`."""
    ref = maps["routers.auth"].resolve("CurrentUser")
    assert (ref.name, ref.module) == ("CurrentUser", "deps")


def test_relative_import_from_root_module(maps):
    """main.py 의 `from .errors import OrderNotFound` (package 가 빈 문자열)."""
    ref = maps["main"].resolve("OrderNotFound")
    assert (ref.name, ref.module) == ("OrderNotFound", "errors")


def test_aliased_import_keeps_original_name(maps):
    """main.py 의 `from .routers.auth import router as auth_router`.

    지역 이름은 auth_router 지만 원본 심볼은 routers.auth 의 router 다.
    이걸 놓치면 include_router 가 어느 라우터를 마운트하는지 알 수 없다.
    """
    ref = maps["main"].resolve("auth_router")
    assert (ref.name, ref.module) == ("router", "routers.auth")


def test_third_party_import_is_recorded_with_its_module(maps):
    ref = maps["routers.auth"].resolve("Depends")
    assert (ref.name, ref.module) == ("Depends", "fastapi")


def test_unknown_name_returns_none(maps):
    assert maps["routers.auth"].resolve("NeverImported") is None


def test_package_init_anchors_one_level_higher():
    """`__init__.py` 는 자기 자신이 패키지다.

    모듈 경로를 기준으로 잡으면 여기서 한 단계 어긋난다.
    """
    pkg = _module("from .auth import router", "routers", is_package=True)
    ref = build_import_map(pkg).resolve("router")
    assert ref.module == "routers.auth"


def test_module_alias_resolves_attribute_access():
    module = _module("import services.auth_service as svc", "main")
    ref = build_import_map(module).resolve_attribute("svc", "authenticate")
    assert (ref.name, ref.module) == ("authenticate", "services.auth_service")


def test_imported_module_object_resolves_attribute_access():
    module = _module("from services import auth_service", "main")
    ref = build_import_map(module).resolve_attribute("auth_service", "authenticate")
    assert (ref.name, ref.module) == ("authenticate", "services.auth_service")


def test_star_import_is_ignored():
    module = _module("from schemas.auth import *", "main")
    assert build_import_map(module).symbols == {}
