"""라우트 선언 자체에서 읽어 내는 것 — 경로, 메서드, 성공 상태코드, 응답 모델.

가장 먼저 실행되며 다른 추출기들이 쓸 뼈대를 세운다. 특히 `path` 는 여기서
prefix 를 합성해 완전한 형태로 만들어 두어야, 뒤의 파라미터 추출기가 경로
템플릿(`{order_id}`)을 보고 path 파라미터를 가려낼 수 있다.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from testweaver.analyzer.ast_utils import (
    all_decorator_calls,
    argument_of,
    keyword_of,
    literal_value,
    resolve_status_constant,
    split_attribute_call,
)
from testweaver.analyzer.extractors.base import ExtractionContext
from testweaver.analyzer.index.context import ProjectIndex
from testweaver.analyzer.index.file_index import ModuleInfo
from testweaver.analyzer.index.router_graph import (
    DependencySite,
    RouterDef,
    RouteVariant,
)
from testweaver.analyzer.models import (
    AnalysisNote,
    HttpMethod,
    NoteCode,
    NoteLevel,
)

#: 데코레이터 이름이 곧 메서드인 형태(@router.get). 소문자로 비교한다.
_METHOD_DECORATORS = {method.value.lower(): method for method in HttpMethod}

#: 메서드를 인자로 받는 형태(@router.api_route(..., methods=["GET"])).
_GENERIC_DECORATOR = "api_route"

#: 동적으로 라우트를 다는 형태. 정적 분석으로는 경로를 알 수 없다.
_DYNAMIC_REGISTRARS = {"add_api_route", "add_route", "add_websocket_route"}

#: FastAPI 가 status_code 를 명시하지 않았을 때 쓰는 값.
_DEFAULT_SUCCESS_STATUS = 200


@dataclass(slots=True)
class RouteSite:
    """소스에서 발견한 라우트 선언 한 건."""

    module: ModuleInfo
    handler: ast.FunctionDef | ast.AsyncFunctionDef
    decorator: ast.Call
    method: HttpMethod
    router: RouterDef | None
    #: 이 라우트에 적용할 prefix. 라우터가 여러 곳에 마운트되면 사이트도
    #: 그만큼 생긴다. FastAPI 가 실제로 라우트를 여러 벌 만들기 때문이다.
    prefix: str = ""
    inherited_dependencies: list[DependencySite] = field(default_factory=list)
    inherited_tags: list[str] = field(default_factory=list)


def find_routes(
    module: ModuleInfo, index: ProjectIndex, notes: list[AnalysisNote] | None = None
) -> Iterator[RouteSite]:
    """모듈 안의 라우트 선언을 전부 찾는다.

    데코레이터가 여러 개 붙어 있어도(`@limiter.limit(...)` 등) 라우트
    데코레이터만 골라내며, 한 핸들러에 메서드 데코레이터가 여러 개면
    메서드마다 하나씩 만든다.
    """
    for node in ast.walk(module.tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield from _routes_of(node, module, index)
        elif isinstance(node, ast.Call):
            _warn_dynamic(node, module, notes)


def _routes_of(
    handler: ast.FunctionDef | ast.AsyncFunctionDef,
    module: ModuleInfo,
    index: ProjectIndex,
) -> Iterator[RouteSite]:
    for decorator in all_decorator_calls(handler):
        receiver, attribute = split_attribute_call(decorator)
        if attribute is None:
            continue
        owner = index.resolve(module.path, receiver) if receiver else None
        router = index.routers.routers.get(owner) if owner else None
        app_dependencies = (
            index.routers.app_dependencies.get(owner, []) if owner else []
        )

        # `.get()` 같은 메서드 이름만 보고 일반 데코레이터를 라우트로
        # 오인하지 않는다. 선언부에서 확인된 APIRouter/FastAPI 만 받는다.
        if router is None and owner not in index.routers.app_refs:
            continue

        variants = (
            router.route_variants
            if router
            else [RouteVariant("", app_dependencies, [])]
        )

        method = _METHOD_DECORATORS.get(attribute)
        if method is not None:
            for variant in variants:
                yield RouteSite(
                    module,
                    handler,
                    decorator,
                    method,
                    router,
                    variant.prefix,
                    variant.dependencies,
                    variant.tags,
                )
            continue

        if attribute == _GENERIC_DECORATOR:
            for name in _declared_methods(decorator):
                for variant in variants:
                    yield RouteSite(
                        module,
                        handler,
                        decorator,
                        name,
                        router,
                        variant.prefix,
                        variant.dependencies,
                        variant.tags,
                    )


def _declared_methods(decorator: ast.Call) -> list[HttpMethod]:
    """`methods=["GET", "POST"]` 를 읽는다."""
    declared = literal_value(keyword_of(decorator, "methods"))
    if not isinstance(declared, list | tuple):
        return []
    found = []
    for item in declared:
        if isinstance(item, str) and item.upper() in HttpMethod.__members__:
            found.append(HttpMethod[item.upper()])
    return found


def _warn_dynamic(
    node: ast.Call, module: ModuleInfo, notes: list[AnalysisNote] | None
) -> None:
    """`app.add_api_route(...)` 처럼 런타임에 다는 라우트를 알린다.

    경로가 변수에서 오므로 정적으로는 알아낼 수 없다. 조용히 빠뜨리는
    대신 "여기 놓친 게 있다"고 남긴다.
    """
    if notes is None:
        return
    if split_attribute_call(node)[1] in _DYNAMIC_REGISTRARS:
        notes.append(
            AnalysisNote(
                NoteLevel.WARNING,
                NoteCode.DYNAMIC_ROUTE,
                "런타임에 등록되는 라우트라 경로를 확정할 수 없습니다",
                str(module.path),
                node.lineno,
            )
        )


class RouteExtractor:
    """라우트 데코레이터에서 읽을 수 있는 것을 전부 채운다."""

    name = "route"
    requires: tuple[str, ...] = ()

    def extract(self, context: ExtractionContext) -> None:
        endpoint = context.endpoint
        endpoint.path = self._path(context)
        endpoint.success_status_code = self._success_status(context)
        endpoint.response_model = self._response_model(context)
        endpoint.tags = self._tags(context)
        endpoint.deprecated = (
            literal_value(keyword_of(context.decorator, "deprecated")) is True
        )

        endpoint.source_file = context.module.path
        endpoint.module_path = context.module.module_path
        endpoint.lineno = context.handler.lineno
        endpoint.is_async = isinstance(context.handler, ast.AsyncFunctionDef)

    def _path(self, context: ExtractionContext) -> str:
        declared = literal_value(argument_of(context.decorator, 0, "path"))
        if not isinstance(declared, str):
            context.note(
                NoteLevel.WARNING,
                NoteCode.UNRESOLVED_PATH,
                "경로가 리터럴이 아니라 확정할 수 없습니다",
                context.decorator.lineno,
            )
            declared = ""
        return join_path(context.prefix, declared)

    def _success_status(self, context: ExtractionContext) -> int | None:
        """명시된 status_code 를 읽는다.

        인자 자체가 없으면 FastAPI 기본값 200 이 확정이다. 인자는 있는데
        해석하지 못한 경우에만 None 을 둔다. 200 으로 뭉개면 틀린 기대값이
        조용히 생성된다.
        """
        declared = keyword_of(context.decorator, "status_code")
        if declared is None:
            return _DEFAULT_SUCCESS_STATUS
        status = resolve_status_constant(declared)
        if status is None:
            context.note(
                NoteLevel.WARNING,
                NoteCode.UNRESOLVED_STATUS,
                "status_code 를 상수로 해석하지 못했습니다",
                context.decorator.lineno,
            )
        return status

    def _response_model(self, context: ExtractionContext):
        declared = keyword_of(context.decorator, "response_model")
        if declared is None:
            return None
        # list[OrderOut] 처럼 감싸여 있어도 안쪽 모델을 가리키게 한다.
        from testweaver.analyzer.ast_utils import unwrap_annotation

        info = unwrap_annotation(declared)
        return context.resolve(info.model_name) if info.model_name else None

    def _tags(self, context: ExtractionContext) -> list[str]:
        inherited = context.inherited_tags
        declared = literal_value(keyword_of(context.decorator, "tags"))
        own = (
            [tag for tag in declared if isinstance(tag, str)]
            if isinstance(declared, list | tuple)
            else []
        )
        return [*inherited, *own]


#: `{file_path:path}` 처럼 이름 뒤에 붙는 변환기.
_PATH_CONVERTER = re.compile(r"\{([^:}]+):[^}]*\}")


def join_path(prefix: str, path: str) -> str:
    """prefix 와 라우트 경로를 FastAPI 와 같은 규칙으로 잇는다.

    ("/api/v1/orders", "")            → "/api/v1/orders"
    ("/api/v1/orders", "/{order_id}") → "/api/v1/orders/{order_id}"
    ("",               "/health")     → "/health"
    ("",               "/{p:path}")   → "/{p}"

    변환기(`:path`)는 라우팅 규칙이지 URL 의 일부가 아니다. FastAPI 도
    스펙에서 떼어 내며, 남겨 두면 생성된 테스트가 없는 주소를 호출한다.
    """
    joined = f"{prefix.rstrip('/')}{path}"
    return _PATH_CONVERTER.sub(r"{\1}", joined) or "/"
