"""엔드포인트가 낼 수 있는 예외를 모은다.

핸들러 본문만 보면 거의 아무것도 못 찾는다. 실무 코드에서 예외는 서비스
계층이 던지고 핸들러는 그걸 부르기만 한다.

    def login(payload):              # raise 가 하나도 없다
        return authenticate(payload) # ← 여기서 401 과 423 이 난다

그래서 호출 그래프를 따라 들어가고, 의존성 함수도 함께 훑는다
(`get_current_user` 의 401 은 핸들러 어디에도 안 보인다).
"""

from __future__ import annotations

import ast

from testweaver.analyzer.ast_utils import (
    argument_of,
    iter_runtime_nodes,
    literal_value,
    resolve_status_constant,
)
from testweaver.analyzer.extractors.base import ExtractionContext
from testweaver.analyzer.index.symbol_index import FunctionDef
from testweaver.analyzer.models import ExceptionFlow, NoteCode, NoteLevel

#: 호출 그래프를 따라 들어가는 깊이 제한. 이보다 깊으면 그 예외가 정말 이
#: 엔드포인트에서 나는지 확신하기 어렵고, 케이스만 늘어난다.
_MAX_DEPTH = 3

#: 상태코드와 상세를 인자로 받는 예외. FastAPI 의 표준 형태다.
_HTTP_EXCEPTIONS = {"HTTPException", "StarletteHTTPException"}


class ExceptionExtractor:
    """핸들러·호출 그래프·의존성에서 발생 가능한 예외를 모은다."""

    name = "exception"
    requires = ("dependency",)

    def extract(self, context: ExtractionContext) -> None:
        flows: list[ExceptionFlow] = []
        visited: set[str] = set()

        self._walk(
            context,
            node=context.handler,
            module_path=context.module.path,
            owner=context.handler.name,
            depth=0,
            flows=flows,
            visited=visited,
        )

        # 의존성이 던지는 예외도 이 엔드포인트에서 난다.
        for dependency in context.endpoint.dependencies:
            target = context.index.find_callable(dependency.source)
            if target is None:
                continue
            self._walk(
                context,
                node=target.node,
                module_path=target.module.path,
                owner=target.name,
                depth=1,
                flows=flows,
                visited=visited,
            )

        context.endpoint.exceptions = flows

    def _walk(
        self,
        context: ExtractionContext,
        node: ast.AST,
        module_path,
        owner: str,
        depth: int,
        flows: list[ExceptionFlow],
        visited: set[str],
    ) -> None:
        children = (
            iter_runtime_nodes(node)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            else ast.walk(node)
        )
        for child in children:
            if isinstance(child, ast.Raise):
                flow = self._flow_of(context, child, module_path, owner, depth)
                if flow is not None:
                    flows.append(flow)
            elif isinstance(child, ast.Call) and depth < _MAX_DEPTH:
                self._follow(context, child, module_path, depth, flows, visited)

    def _follow(
        self,
        context: ExtractionContext,
        call: ast.Call,
        module_path,
        depth: int,
        flows: list[ExceptionFlow],
        visited: set[str],
    ) -> None:
        """프로젝트 안의 함수 호출이면 그 안으로 들어간다."""
        ref = context.index.resolve_expr(module_path, call.func)
        target: FunctionDef | None = context.index.find_function(ref)
        if target is None or target.qualified_name in visited:
            return
        visited.add(target.qualified_name)
        self._walk(
            context,
            node=target.node,
            module_path=target.module.path,
            owner=target.name,
            depth=depth + 1,
            flows=flows,
            visited=visited,
        )

    def _flow_of(
        self,
        context: ExtractionContext,
        node: ast.Raise,
        module_path,
        owner: str,
        depth: int,
    ) -> ExceptionFlow | None:
        if not isinstance(node.exc, ast.Call):
            return None  # 맨 raise 는 이미 잡힌 예외를 다시 던지는 것이다.

        ref = context.index.resolve_expr(module_path, node.exc.func)
        name = ref.name if ref else ast.unparse(node.exc.func)

        if name in _HTTP_EXCEPTIONS:
            status = resolve_status_constant(argument_of(node.exc, 0, "status_code"))
            detail = literal_value(argument_of(node.exc, 1, "detail"))
            return ExceptionFlow(
                exception_type=name,
                status_code=status,
                error_code=detail if isinstance(detail, str) else None,
                raised_in=owner,
                depth=depth,
                resolved=status is not None,
            )

        # 커스텀 예외는 전역 핸들러가 상태코드를 정한다.
        status = context.index.status_for_exception(ref)
        if status is None:
            context.note(
                NoteLevel.INFO,
                NoteCode.UNRESOLVED_STATUS,
                f"{name} 의 상태코드를 정하는 핸들러를 찾지 못했습니다",
                node.lineno,
            )
        return ExceptionFlow(
            exception_type=name,
            status_code=status,
            raised_in=owner,
            depth=depth,
            resolved=status is not None,
        )


def unresolved_exceptions(flows: list[ExceptionFlow]) -> list[ExceptionFlow]:
    """상태코드를 확정하지 못한 예외들. 매트릭스에서 null 이 되는 것들이다."""
    return [flow for flow in flows if not flow.resolved]
