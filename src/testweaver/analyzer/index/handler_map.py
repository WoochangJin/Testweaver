"""커스텀 예외 → 상태코드 매핑.

`raise OrderNotFound(order_id)` 만 봐서는 응답이 몇 번인지 알 수 없다.
그 답은 전혀 다른 파일의 `@app.exception_handler(OrderNotFound)` 안에 있다.

이 표가 없으면 커스텀 예외를 쓰는 엔드포인트의 실패 케이스는 전부
`expected_status: null` 이 된다.
"""

from __future__ import annotations

import ast

from testweaver.analyzer.ast_utils import (
    argument_of,
    attribute_or_name,
    iter_runtime_nodes,
    keyword_of,
    resolve_status_constant,
    split_attribute_call,
)
from testweaver.analyzer.index.file_index import ModuleInfo
from testweaver.analyzer.index.import_map import ImportMap
from testweaver.analyzer.models import AnalysisNote, NoteCode, NoteLevel, SymbolRef

_DECORATOR = "exception_handler"


def index_exception_handlers(
    modules: dict[object, ModuleInfo],
    import_maps: dict[object, ImportMap],
    notes: list[AnalysisNote] | None = None,
) -> dict[SymbolRef, int]:
    """`@app.exception_handler(Exc)` 를 찾아 예외별 상태코드를 모은다.

    핸들러 본문에서 `return` 되는 응답의 `status_code=` 를 그 예외의
    상태코드로 본다. 대부분의 핸들러는 응답을 하나만 만든다.
    """
    mapping: dict[SymbolRef, int] = {}

    for module in modules.values():
        imports = import_maps[module.path]
        for node in ast.walk(module.tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if split_attribute_call(decorator)[1] != _DECORATOR:
                    continue

                exception = _exception_ref(decorator, module, imports)
                if exception is None:
                    continue

                status = _status_in_body(node)
                if status is None:
                    _note(
                        notes,
                        module,
                        node.lineno,
                        f"{exception.name} 핸들러의 상태코드를 확정하지 못했습니다",
                    )
                    continue
                mapping[exception] = status

    return mapping


def _exception_ref(
    decorator: ast.Call, module: ModuleInfo, imports: ImportMap
) -> SymbolRef | None:
    """데코레이터 인자의 예외 클래스를 심볼로 해석한다.

    `raise` 쪽도 같은 방식으로 해석하므로 두 참조가 같은 키가 된다.
    """
    target = argument_of(decorator, 0, "exc_class_or_status_code")
    if isinstance(target, ast.Name):
        return imports.resolve(target.id) or SymbolRef(
            name=target.id, module=module.module_path, file=module.path
        )
    if isinstance(target, ast.Attribute):
        base = attribute_or_name(target.value)
        if base:
            return imports.resolve_attribute(base, target.attr)
    return None


def _status_in_body(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    """`return` 되는 응답의 `status_code=` 를 찾는다.

    `ast.walk(fn)`으로 본문 전체를 훑으면 로깅 호출처럼 실제 응답과 무관한
    `status_code=` 를 먼저 주워버릴 수 있고, 실행되지 않는 중첩 함수 본문까지
    내려가 버린다 (`iter_runtime_nodes` 의 docstring 참고). 그래서 `return`
    표현식으로 범위를 좁힌다.

    `return resp` 처럼 변수를 그대로 반환하는 핸들러도 있으므로, 대입식까지
    한 겹 역추적한다 (재대입되면 return 시점에 유효한 마지막 값을 쓴다).
    """
    last_assign: dict[str, ast.expr] = {}
    for node in iter_runtime_nodes(fn):
        if isinstance(node, ast.Assign | ast.AnnAssign) and node.value is not None:
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                if isinstance(target, ast.Name):
                    last_assign[target.id] = node.value
            continue

        if not isinstance(node, ast.Return) or node.value is None:
            continue

        status = _status_in_expr(node.value)
        if status is not None:
            return status

        if isinstance(node.value, ast.Name):
            source = last_assign.get(node.value.id)
            if source is not None:
                status = _status_in_expr(source)
                if status is not None:
                    return status

    return None


def _status_in_expr(expr: ast.expr) -> int | None:
    for node in ast.walk(expr):
        if not isinstance(node, ast.Call):
            continue
        argument = keyword_of(node, "status_code")
        if argument is None:
            continue
        status = resolve_status_constant(argument)
        if status is not None:
            return status
    return None


def _note(
    notes: list[AnalysisNote] | None, module: ModuleInfo, line: int, message: str
) -> None:
    if notes is not None:
        notes.append(
            AnalysisNote(
                NoteLevel.WARNING,
                NoteCode.UNRESOLVED_STATUS,
                message,
                str(module.path),
                line,
            )
        )
