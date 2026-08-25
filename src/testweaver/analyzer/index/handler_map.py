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
    iter_functions,
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

    핸들러 본문에서 첫 번째로 해석되는 `status_code=` 를 그 예외의 상태코드로
    본다. 대부분의 핸들러는 응답을 하나만 만든다.
    """
    mapping: dict[SymbolRef, int] = {}

    for module in modules.values():
        imports = import_maps[module.path]
        for node in iter_functions(module.tree):
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


def _status_in_body(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> int | None:
    """핸들러가 실제로 반환하는 응답에서 상태코드를 찾는다.

    ``ast.walk(fn)`` 은 실행되지 않는 중첩 함수·클래스의 본문까지 내려가
    거기 있는 ``return`` 을 핸들러 자신의 응답으로 오인할 수 있다.
    ``iter_runtime_nodes`` 로 핸들러가 실제로 실행하는 노드만 순회한다.
    """
    for node in iter_runtime_nodes(fn):
        if not isinstance(node, ast.Return) or node.value is None:
            continue

        for returned_node in ast.walk(node.value):
            if not isinstance(returned_node, ast.Call):
                continue

            argument = keyword_of(returned_node, "status_code")
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
