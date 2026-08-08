"""모듈 최상위에 선언된 리터럴 상수와 클래스 인스턴스.

실무 코드는 값을 그 자리에 적지 않는다.

    API_PREFIX = "/api"
    app.include_router(router, prefix=API_PREFIX)

`ast.literal_eval` 은 이름을 따라가지 못하므로 prefix 가 빈 문자열이 되고,
그러면 그 라우터에 달린 모든 경로가 어긋난다. 상수를 미리 모아 두면 이름
하나를 값으로 되돌릴 수 있다.

같은 이유로 인스턴스도 모은다.

    throttle = RateLimiter(limit=10)
    Depends(throttle)

`throttle` 은 함수가 아니라 변수라, 이걸 클래스까지 되짚지 못하면 그
`__call__` 이 선언한 파라미터를 통째로 놓친다.
"""

from __future__ import annotations

import ast
from typing import Any

from testweaver.analyzer.ast_utils import UNRESOLVED, attribute_or_name, literal_value
from testweaver.analyzer.index.file_index import ModuleInfo
from testweaver.analyzer.index.import_map import ImportMap


def index_constants(modules: dict[Any, ModuleInfo]) -> dict[str, Any]:
    """모듈 최상위의 리터럴 대입을 완전 이름으로 색인한다.

    함수 안의 지역 변수는 담지 않는다. 이름이 겹쳐 키가 무너지고, 설정
    상수는 거의 항상 모듈 최상위에 있다.
    """
    found: dict[str, Any] = {}
    for module in modules.values():
        for statement in module.tree.body:
            for name, value in _assignments(statement):
                literal = literal_value(value)
                if literal is not UNRESOLVED:
                    found[_qualified(module, name)] = literal
    return found


def index_instances(modules: dict[Any, ModuleInfo]) -> dict[str, str]:
    """`x = SomeClass(...)` 형태를 {완전 이름: 클래스 이름} 으로 색인한다."""
    found: dict[str, str] = {}
    for module in modules.values():
        for statement in module.tree.body:
            for name, value in _assignments(statement):
                if isinstance(value, ast.Call):
                    class_name = attribute_or_name(value.func)
                    if class_name and class_name[:1].isupper():
                        found[_qualified(module, name)] = class_name
    return found


def resolve_value(
    node: ast.expr | None,
    module: ModuleInfo,
    imports: ImportMap,
    constants: dict[str, Any],
) -> Any:
    """식을 값으로 바꾼다. 리터럴이 아니면 상수 이름으로 한 번 더 시도한다.

    `settings.API_PREFIX` 처럼 속성 접근이면 값을 알 수 없으므로 UNRESOLVED 다.
    """
    literal = literal_value(node)
    if literal is not UNRESOLVED:
        return literal

    if not isinstance(node, ast.Name):
        return UNRESOLVED

    # 같은 모듈에 선언된 상수.
    same_module = constants.get(_qualified(module, node.id))
    if same_module is not None:
        return same_module

    # 다른 모듈에서 import 한 상수.
    imported = imports.resolve(node.id)
    if imported is not None and imported.module:
        key = f"{imported.module}.{imported.name}" if imported.module else imported.name
        if key in constants:
            return constants[key]
    return UNRESOLVED


def _assignments(statement: ast.stmt):
    """`x = 1` 과 `x: str = "a"` 에서 (이름, 값) 쌍을 뽑는다."""
    if isinstance(statement, ast.Assign):
        for target in statement.targets:
            if isinstance(target, ast.Name):
                yield target.id, statement.value
    elif (
        isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
        and statement.value is not None
    ):
        yield statement.target.id, statement.value


def _qualified(module: ModuleInfo, name: str) -> str:
    return f"{module.module_path}.{name}" if module.module_path else name
