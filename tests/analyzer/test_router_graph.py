import ast
from pathlib import Path

import pytest

from tests.conftest import FIXTURE_ROOT
from testweaver.analyzer.index.file_index import ModuleInfo, collect_modules
from testweaver.analyzer.index.import_map import build_import_map
from testweaver.analyzer.index.router_graph import build_router_graph
from testweaver.analyzer.models import NoteCode


def _graph_of(sources: dict[str, str], notes: list | None = None):
    """모듈 경로 → 소스 맵으로 작은 프로젝트를 흉내 낸다."""
    modules = {
        Path(f"{name}.py"): ModuleInfo(
            path=Path(f"{name}.py"), module_path=name, tree=ast.parse(source)
        )
        for name, source in sources.items()
    }
    import_maps = {m.path: build_import_map(m) for m in modules.values()}
    return build_router_graph(modules, import_maps, notes=notes)


@pytest.fixture(scope="module")
def fixture_graph():
    modules = collect_modules(FIXTURE_ROOT)
    import_maps = {m.path: build_import_map(m) for m in modules.values()}
    return build_router_graph(modules, import_maps, notes=[])


# ─────────────── 실제 픽스처 ───────────────


def test_composes_mount_prefix_with_router_prefix(fixture_graph):
    """이 단계 전체의 존재 이유. /auth 와 /api/v1 이 합쳐져야 한다."""
    assert fixture_graph.get("routers.auth", "router").full_prefix == "/api/v1/auth"
    assert fixture_graph.get("routers.orders", "router").full_prefix == "/api/v1/orders"


def test_app_is_detected(fixture_graph):
    assert any(ref.name == "app" for ref in fixture_graph.app_refs)


def test_router_owns_its_declared_tags(fixture_graph):
    assert fixture_graph.get("routers.auth", "router").own_tags == ["auth"]


def test_both_routers_are_mounted(fixture_graph):
    assert len(fixture_graph.mounts) == 2
    assert all(edge.parent is None for edge in fixture_graph.mounts), "둘 다 앱에 직접"


# ─────────────── 합성 규칙 ───────────────


def test_nested_routers_accumulate_prefixes():
    graph = _graph_of(
        {
            "routers.items": "from fastapi import APIRouter\nsub = APIRouter(prefix='/items')\n",
            "routers.shop": (
                "from fastapi import APIRouter\n"
                "from .items import sub\n"
                "shop = APIRouter(prefix='/shop')\n"
                "shop.include_router(sub, prefix='/v2')\n"
            ),
            "main": (
                "from fastapi import FastAPI\n"
                "from .routers.shop import shop\n"
                "app = FastAPI()\n"
                "app.include_router(shop, prefix='/api')\n"
            ),
        }
    )
    assert graph.get("routers.shop", "shop").full_prefix == "/api/shop"
    assert graph.get("routers.items", "sub").full_prefix == "/api/shop/v2/items"


def test_unmounted_router_keeps_only_its_own_prefix():
    graph = _graph_of(
        {"orphan": "from fastapi import APIRouter\nr = APIRouter(prefix='/orphan')\n"}
    )
    router = graph.get("orphan", "r")
    assert router.full_prefix == "/orphan"
    assert router.is_mounted is False


def test_trailing_slash_in_prefix_is_normalised():
    graph = _graph_of(
        {
            "r": "from fastapi import APIRouter\nr = APIRouter(prefix='/auth/')\n",
            "main": (
                "from fastapi import FastAPI\n"
                "from .r import r\n"
                "app = FastAPI()\n"
                "app.include_router(r, prefix='/api/')\n"
            ),
        }
    )
    assert graph.get("r", "r").full_prefix == "/api/auth"


def test_router_without_prefix_inherits_mount_prefix_only():
    graph = _graph_of(
        {
            "r": "from fastapi import APIRouter\nr = APIRouter()\n",
            "main": (
                "from fastapi import FastAPI\n"
                "from .r import r\n"
                "app = FastAPI()\n"
                "app.include_router(r, prefix='/api/v1')\n"
            ),
        }
    )
    assert graph.get("r", "r").full_prefix == "/api/v1"


# ─────────────── 의존성 상속 ───────────────


def test_router_and_mount_dependencies_are_inherited():
    """APIRouter(dependencies=...) 로 인증을 걸면 핸들러 시그니처엔 안 보인다."""
    graph = _graph_of(
        {
            "r": (
                "from fastapi import APIRouter, Depends\n"
                "r = APIRouter(prefix='/a', dependencies=[Depends(verify)])\n"
            ),
            "main": (
                "from fastapi import Depends, FastAPI\n"
                "from .r import r\n"
                "app = FastAPI(dependencies=[Depends(global_dep)])\n"
                "app.include_router(r, dependencies=[Depends(mount_dep)])\n"
            ),
        }
    )
    router = graph.get("r", "r")
    rendered = [ast.unparse(node) for node in router.effective_dependencies]
    assert rendered == [
        "Depends(global_dep)",
        "Depends(mount_dep)",
        "Depends(verify)",
    ]


def test_tags_are_inherited_from_mount():
    graph = _graph_of(
        {
            "r": "from fastapi import APIRouter\nr = APIRouter(tags=['own'])\n",
            "main": (
                "from fastapi import FastAPI\n"
                "from .r import r\n"
                "app = FastAPI()\n"
                "app.include_router(r, tags=['mounted'])\n"
            ),
        }
    )
    assert graph.get("r", "r").effective_tags == ["mounted", "own"]


# ─────────────── 해석 실패 ───────────────


def test_non_literal_prefix_reports_note():
    notes: list = []
    _graph_of(
        {
            "r": "from fastapi import APIRouter\nr = APIRouter()\n",
            "main": (
                "from fastapi import FastAPI\n"
                "from .r import r\n"
                "app = FastAPI()\n"
                "app.include_router(r, prefix=settings.API_PREFIX)\n"
            ),
        },
        notes,
    )
    assert NoteCode.UNRESOLVED_PREFIX in [n.code for n in notes]


def test_multiple_mounts_produce_every_prefix():
    """FastAPI 는 마운트한 만큼 라우트를 만든다. 하나만 남기면 절반을 잃는다."""
    notes: list = []
    graph = _graph_of(
        {
            "r": "from fastapi import APIRouter\nr = APIRouter(prefix='/x')\n",
            "main": (
                "from fastapi import FastAPI\n"
                "from .r import r\n"
                "app = FastAPI()\n"
                "app.include_router(r, prefix='/v1')\n"
                "app.include_router(r, prefix='/v2')\n"
            ),
        },
        notes,
    )
    assert graph.get("r", "r").full_prefixes == ["/v1/x", "/v2/x"]


def test_cyclic_mount_does_not_recurse_forever():
    notes: list = []
    graph = _graph_of(
        {
            "a": (
                "from fastapi import APIRouter\n"
                "from .b import b\n"
                "a = APIRouter(prefix='/a')\n"
                "a.include_router(b)\n"
            ),
            "b": (
                "from fastapi import APIRouter\n"
                "from .a import a\n"
                "b = APIRouter(prefix='/b')\n"
                "b.include_router(a)\n"
            ),
        },
        notes,
    )
    assert graph.get("a", "a") is not None, "무한 재귀 없이 끝나야 한다"
