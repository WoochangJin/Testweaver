"""의존성 주입 지점을 모은다.

네 곳에 선언될 수 있고 넷 다 실제로 적용된다.

    app = FastAPI(dependencies=[...])                        앱 전체
    router = APIRouter(dependencies=[...])                   라우터 전체
    @router.get("/x", dependencies=[...])                    이 라우트만
    def handler(user: Annotated[User, Depends(get_user)])    이 핸들러 인자

핸들러 인자만 보면 라우터 단위로 인증을 건 프로젝트는 인증 여부를 전혀 알 수
없다. 그리고 `Annotated[User, Depends(...)]` 는 기본값이 없는 문법이라,
인자의 기본값만 뒤지면 현재 FastAPI 의 주류 표기를 통째로 놓친다.
"""

from __future__ import annotations

import ast

from testweaver.analyzer.ast_utils import (
    UNRESOLVED,
    argument_of,
    iter_all_args,
    keyword_of,
    literal_value,
    unwrap_annotation,
)
from testweaver.analyzer.extractors.base import ExtractionContext
from testweaver.analyzer.extractors.fields import (
    DEPENDENCY_MARKERS,
    find_marker,
    marker_name,
)
from testweaver.analyzer.models import (
    DependencyNode,
    DependencyOrigin,
    NoteCode,
    NoteLevel,
    SymbolRef,
)

#: 전이 의존성을 따라가는 깊이 제한.
_MAX_DEPTH = 3


class DependencyExtractor:
    """핸들러·라우트·라우터·앱 네 층위의 의존성을 모두 수집한다."""

    name = "dependency"
    requires = ("route",)

    def extract(self, context: ExtractionContext) -> None:
        collected: list[DependencyNode] = []
        seen: set[SymbolRef] = set()

        # 라우터와 앱에서 물려받은 것 (router_graph 가 이미 합쳐 뒀다).
        inherited = context.router.effective_dependencies if context.router else []
        for item in inherited:
            self._add(context, item, DependencyOrigin.ROUTER, collected, seen)

        # 라우트 데코레이터에 붙은 것.
        for item in _list_items(keyword_of(context.decorator, "dependencies")):
            self._add(context, item, DependencyOrigin.ROUTE, collected, seen)

        # 핸들러 인자.
        for arg, default in iter_all_args(context.handler):
            info = unwrap_annotation(arg.annotation)
            marker = find_marker(default, info.metadata, DEPENDENCY_MARKERS)
            if marker is not None:
                self._add(
                    context, marker, DependencyOrigin.HANDLER, collected, seen, arg.arg
                )

        context.endpoint.dependencies = collected

    def _add(
        self,
        context: ExtractionContext,
        marker: ast.expr,
        origin: DependencyOrigin,
        collected: list[DependencyNode],
        seen: set[SymbolRef],
        arg_name: str | None = None,
        depth: int = 0,
    ) -> None:
        if not isinstance(marker, ast.Call):
            return
        target = argument_of(marker, 0, "dependency")
        ref = context.resolve_expr(target)
        if ref is None or ref in seen:
            return
        seen.add(ref)

        in_project = context.index.is_in_project(ref)
        if not in_project:
            context.note(
                NoteLevel.INFO,
                NoteCode.EXTERNAL_SYMBOL,
                f"{ref} 는 프로젝트 밖이라 오버라이드 대상을 특정할 수 없습니다",
                marker.lineno,
            )

        collected.append(
            DependencyNode(
                name=arg_name or ref.name,
                source=ref,
                origin=origin,
                scopes=_scopes(marker),
                overridable=in_project,
            )
        )

        if depth < _MAX_DEPTH:
            self._walk_transitive(context, ref, origin, collected, seen, depth)

    def _walk_transitive(
        self,
        context: ExtractionContext,
        ref: SymbolRef,
        origin: DependencyOrigin,
        collected: list[DependencyNode],
        seen: set[SymbolRef],
        depth: int,
    ) -> None:
        """의존성이 다시 의존하는 것까지 따라간다.

        `require_admin` 이 `get_current_user` 에 의존하면 그 401 도 이
        엔드포인트에서 날 수 있다. 예외 수집이 이 목록을 쓴다.
        """
        target = context.index.find_function(ref)
        if target is None:
            return
        for arg, default in iter_all_args(target.node):
            info = unwrap_annotation(arg.annotation)
            marker = find_marker(default, info.metadata, DEPENDENCY_MARKERS)
            if marker is None:
                continue
            nested = context.index.resolve_expr(
                target.module.path, argument_of(marker, 0, "dependency")
            )
            if nested is None or nested in seen:
                continue
            seen.add(nested)
            collected.append(
                DependencyNode(
                    name=arg.arg,
                    source=nested,
                    origin=origin,
                    overridable=context.index.is_in_project(nested),
                )
            )
            self._walk_transitive(context, nested, origin, collected, seen, depth + 1)


def _scopes(marker: ast.Call) -> list[str]:
    """`Security(dep, scopes=["admin"])` 의 권한 범위."""
    if marker_name(marker) != "Security":
        return []
    declared = literal_value(keyword_of(marker, "scopes"))
    if declared is UNRESOLVED or not isinstance(declared, list | tuple):
        return []
    return [scope for scope in declared if isinstance(scope, str)]


def _list_items(node: ast.expr | None) -> list[ast.expr]:
    return list(node.elts) if isinstance(node, ast.List) else []
