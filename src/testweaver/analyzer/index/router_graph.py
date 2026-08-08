"""라우터 마운트 그래프 — 엔드포인트의 실제 경로를 결정한다.

FastAPI 에서 한 라우트의 진짜 경로는 세 곳에 나뉘어 적힌다.

    main.py          app.include_router(auth_router, prefix="/api/v1")
    routers/auth.py  router = APIRouter(prefix="/auth")
                     @router.post("/login")

`routers/auth.py` 하나만 봐서는 `/login` 밖에 알 수 없다. 세 파일의 정보를
합쳐야 `/api/v1/auth/login` 이 나오고, 그러지 못하면 생성된 테스트가 전부
404 를 받는다.

prefix 뿐 아니라 라우터·마운트 단위로 걸린 의존성과 태그도 함께 물려받는다.
`APIRouter(dependencies=[Depends(verify)])` 로 인증을 건 프로젝트는 핸들러
시그니처만 봐서는 인증 여부를 알 수 없다.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from testweaver.analyzer.ast_utils import (
    UNRESOLVED,
    argument_of,
    attribute_or_name,
    keyword_of,
    literal_value,
    split_attribute_call,
)
from testweaver.analyzer.index.file_index import ModuleInfo
from testweaver.analyzer.index.import_map import ImportMap
from testweaver.analyzer.models import AnalysisNote, NoteCode, NoteLevel, SymbolRef

_ROUTER_FACTORY = "APIRouter"
_APP_FACTORY = "FastAPI"


@dataclass(slots=True)
class RouterDef:
    """`APIRouter(...)` 로 만들어진 라우터 하나."""

    ref: SymbolRef
    module: ModuleInfo
    own_prefix: str = ""
    own_dependencies: list[ast.expr] = field(default_factory=list)
    own_tags: list[str] = field(default_factory=list)

    #: 마운트 사슬을 모두 반영한 결과. `resolve_prefixes()` 가 채운다.
    full_prefix: str = ""
    inherited_dependencies: list[ast.expr] = field(default_factory=list)
    inherited_tags: list[str] = field(default_factory=list)
    is_mounted: bool = False

    @property
    def effective_dependencies(self) -> list[ast.expr]:
        """이 라우터의 라우트에 실제로 적용되는 의존성 전부."""
        return [*self.inherited_dependencies, *self.own_dependencies]

    @property
    def effective_tags(self) -> list[str]:
        return [*self.inherited_tags, *self.own_tags]


@dataclass(slots=True)
class MountEdge:
    """`include_router(...)` 호출 한 건. `parent` 가 None 이면 앱에 직접 붙은 것."""

    parent: SymbolRef | None
    child: SymbolRef
    prefix: str = ""
    dependencies: list[ast.expr] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    module: ModuleInfo | None = None
    lineno: int = 0


@dataclass(slots=True)
class RouterGraph:
    routers: dict[SymbolRef, RouterDef] = field(default_factory=dict)
    mounts: list[MountEdge] = field(default_factory=list)
    app_refs: set[SymbolRef] = field(default_factory=set)
    app_dependencies: list[ast.expr] = field(default_factory=list)

    def get(self, module_path: str, var_name: str) -> RouterDef | None:
        return self.routers.get(SymbolRef(name=var_name, module=module_path))


def build_router_graph(
    modules: dict[object, ModuleInfo],
    import_maps: dict[object, ImportMap],
    notes: list[AnalysisNote] | None = None,
) -> RouterGraph:
    """라우터 정의와 마운트를 수집한 뒤 최종 prefix 를 계산한다."""
    graph = RouterGraph()
    for module in modules.values():
        _collect_definitions(module, graph)
    for module in modules.values():
        _collect_mounts(module, import_maps[module.path], graph, notes)
    resolve_prefixes(graph, notes)
    return graph


# ─────────────────────────── 수집 ───────────────────────────


def _collect_definitions(module: ModuleInfo, graph: RouterGraph) -> None:
    """`x = APIRouter(...)` 와 `app = FastAPI(...)` 를 찾는다."""
    for node in ast.walk(module.tree):
        target, call = _assignment_call(node)
        if target is None or call is None:
            continue
        factory = attribute_or_name(call.func)
        ref = SymbolRef(name=target, module=module.module_path, file=module.path)

        if factory == _ROUTER_FACTORY:
            graph.routers[ref] = RouterDef(
                ref=ref,
                module=module,
                own_prefix=_literal_prefix(call),
                own_dependencies=_dependency_items(call),
                own_tags=_tag_items(call),
            )
        elif factory == _APP_FACTORY:
            graph.app_refs.add(ref)
            graph.app_dependencies.extend(_dependency_items(call))


def _collect_mounts(
    module: ModuleInfo,
    imports: ImportMap,
    graph: RouterGraph,
    notes: list[AnalysisNote] | None,
) -> None:
    """`<대상>.include_router(<라우터>, prefix=...)` 호출을 모은다.

    `create_app()` 안에서 호출하는 경우도 있으므로 최상위만 보지 않고
    트리 전체를 훑는다.
    """
    for node in ast.walk(module.tree):
        if not isinstance(node, ast.Call):
            continue
        receiver, attribute = split_attribute_call(node)
        if attribute != "include_router":
            continue

        child_expr = argument_of(node, 0, "router")
        child = _symbol_of(child_expr, module, imports)
        if child is None:
            _note(
                notes,
                NoteLevel.WARNING,
                NoteCode.DYNAMIC_ROUTE,
                "include_router 의 대상 라우터를 해석하지 못했습니다",
                module,
                node.lineno,
            )
            continue

        parent_ref = (
            SymbolRef(name=receiver, module=module.module_path, file=module.path)
            if receiver
            else None
        )
        # 대상이 라우터가 아니면 앱으로 본다 (app.include_router).
        parent = parent_ref if parent_ref in graph.routers else None

        graph.mounts.append(
            MountEdge(
                parent=parent,
                child=child,
                prefix=_literal_prefix(node, notes, module),
                dependencies=_dependency_items(node),
                tags=_tag_items(node),
                module=module,
                lineno=node.lineno,
            )
        )


# ─────────────────────────── prefix 해석 ───────────────────────────


def resolve_prefixes(
    graph: RouterGraph, notes: list[AnalysisNote] | None = None
) -> None:
    """마운트 사슬을 따라 각 라우터의 최종 prefix 와 상속 의존성을 계산한다."""
    edges_by_child: dict[SymbolRef, list[MountEdge]] = {}
    for edge in graph.mounts:
        edges_by_child.setdefault(edge.child, []).append(edge)

    for ref in graph.routers:
        _resolve(ref, graph, edges_by_child, set(), notes)


def _resolve(
    ref: SymbolRef,
    graph: RouterGraph,
    edges_by_child: dict[SymbolRef, list[MountEdge]],
    visiting: set[SymbolRef],
    notes: list[AnalysisNote] | None,
) -> RouterDef | None:
    router = graph.routers.get(ref)
    if router is None or router.is_mounted:
        return router

    if ref in visiting:  # 순환 마운트
        _note(
            notes,
            NoteLevel.WARNING,
            NoteCode.MULTI_MOUNT,
            f"라우터 마운트가 순환합니다: {ref}",
            router.module,
        )
        router.full_prefix = router.own_prefix
        return router

    edges = edges_by_child.get(ref, [])
    if not edges:
        # 어디에도 마운트되지 않은 라우터. 자기 prefix 만 쓴다.
        router.full_prefix = router.own_prefix
        return router

    if len(edges) > 1:
        _note(
            notes,
            NoteLevel.WARNING,
            NoteCode.MULTI_MOUNT,
            f"{ref} 가 {len(edges)}곳에 마운트됐습니다. 첫 번째만 반영합니다",
            router.module,
            edges[0].lineno,
        )

    edge = edges[0]
    visiting.add(ref)
    parent = (
        _resolve(edge.parent, graph, edges_by_child, visiting, notes)
        if edge.parent is not None
        else None
    )
    visiting.discard(ref)

    parent_prefix = parent.full_prefix if parent else ""
    router.full_prefix = _join_prefix(parent_prefix, edge.prefix, router.own_prefix)
    router.inherited_dependencies = [
        *graph.app_dependencies,
        *(parent.effective_dependencies if parent else []),
        *edge.dependencies,
    ]
    router.inherited_tags = [
        *(parent.effective_tags if parent else []),
        *edge.tags,
    ]
    router.is_mounted = True
    return router


def _join_prefix(*parts: str) -> str:
    """prefix 조각들을 이어 붙인다.

    FastAPI 는 prefix 가 `/` 로 끝나는 걸 허용하지 않으므로 끝의 `/` 를 떼고
    붙인다. 빈 조각은 건너뛴다.
    """
    return "".join(part.rstrip("/") for part in parts if part)


# ─────────────────────────── 보조 ───────────────────────────


def _assignment_call(node: ast.AST) -> tuple[str | None, ast.Call | None]:
    """`x = Call(...)` 또는 `x: T = Call(...)` 에서 (이름, 호출)을 꺼낸다."""
    if (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Call)
    ):
        return node.targets[0].id, node.value
    if (
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and isinstance(node.value, ast.Call)
    ):
        return node.target.id, node.value
    return None, None


def _symbol_of(
    expr: ast.expr | None, module: ModuleInfo, imports: ImportMap
) -> SymbolRef | None:
    """식에서 가리키는 심볼을 찾는다.

    auth_router           → import 표를 거쳐 원본 모듈까지
    routers.auth.router   → 모듈 별칭 경유
    """
    if isinstance(expr, ast.Name):
        imported = imports.resolve(expr.id)
        if imported is not None:
            return imported
        return SymbolRef(name=expr.id, module=module.module_path, file=module.path)

    if isinstance(expr, ast.Attribute):
        base = attribute_or_name(expr.value)
        if base:
            return imports.resolve_attribute(base, expr.attr)
    return None


def _literal_prefix(
    call: ast.Call,
    notes: list[AnalysisNote] | None = None,
    module: ModuleInfo | None = None,
) -> str:
    """`prefix=` 인자를 문자열로. 리터럴이 아니면 빈 문자열 + 노트."""
    node = keyword_of(call, "prefix")
    if node is None:
        return ""
    value = literal_value(node)
    if isinstance(value, str):
        return value
    if value is UNRESOLVED:
        _note(
            notes,
            NoteLevel.WARNING,
            NoteCode.UNRESOLVED_PREFIX,
            "prefix 가 리터럴이 아니라 경로를 확정할 수 없습니다",
            module,
            call.lineno,
        )
    return ""


def _dependency_items(call: ast.Call) -> list[ast.expr]:
    """`dependencies=[Depends(...), ...]` 의 원소들. 해석은 하지 않는다."""
    node = keyword_of(call, "dependencies")
    return list(node.elts) if isinstance(node, ast.List) else []


def _tag_items(call: ast.Call) -> list[str]:
    node = keyword_of(call, "tags")
    if not isinstance(node, ast.List):
        return []
    values = [literal_value(element) for element in node.elts]
    return [value for value in values if isinstance(value, str)]


def _note(
    notes: list[AnalysisNote] | None,
    level: NoteLevel,
    code: NoteCode,
    message: str,
    module: ModuleInfo | None = None,
    line: int = 0,
) -> None:
    if notes is not None:
        notes.append(
            AnalysisNote(level, code, message, str(module.path) if module else "", line)
        )
