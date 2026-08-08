"""`Field()` 계열 호출에서 제약과 기본값을 읽는 공용 로직.

Pydantic 의 `Field` 와 FastAPI 의 `Query`/`Path`/`Header`/`Cookie`/`Form`/`Body`
는 같은 이름의 키워드로 같은 제약을 표현한다. 그래서 본문 모델을 읽는
추출기와 파라미터를 읽는 추출기가 이 파일을 공유한다.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

from testweaver.analyzer.ast_utils import (
    UNRESOLVED,
    argument_of,
    attribute_or_name,
    keyword_of,
    literal_value,
)

#: 같은 제약을 가리키는 다른 이름들. Pydantic v1 표기와 항목 개수 제약을 흡수한다.
_ALIASES = {
    "regex": "pattern",
    "min_items": "min_length",
    "max_items": "max_length",
}

#: `Constraint` 로 그대로 옮겨지는 키들.
_CONSTRAINT_KEYS = {
    "min_length",
    "max_length",
    "ge",
    "le",
    "gt",
    "lt",
    "multiple_of",
    "pattern",
}

#: 파라미터 위치를 지정하는 FastAPI 마커.
PARAM_MARKERS = {"Path", "Query", "Header", "Cookie", "Body", "Form", "File"}

#: 의존성 주입 마커. 파라미터가 아니라 의존성으로 다룬다.
DEPENDENCY_MARKERS = {"Depends", "Security"}

#: 값이 아니라 프레임워크 객체가 주입되는 자리. 입력으로 보지 않는다.
FRAMEWORK_TYPES = {
    "Request",
    "Response",
    "WebSocket",
    "BackgroundTasks",
    "HTTPConnection",
    "SecurityScopes",
}


@dataclass(slots=True)
class DefaultInfo:
    """선언된 기본값. `has_default` 가 False 면 필수 항목이다."""

    has_default: bool = False
    value: Any = None
    factory: str | None = None


def field_constraints(call: ast.Call | None) -> dict[str, Any]:
    """`Field(min_length=8, gt=0)` 같은 호출에서 제약 키워드만 뽑는다.

    gt/lt 를 ge/le 로 뭉개지 않는다. OpenAPI 도 exclusiveMinimum 과
    minimum 을 구분하며, 합치면 경계값이 하나씩 어긋난다.
    """
    if call is None:
        return {}
    found: dict[str, Any] = {}
    for keyword in call.keywords:
        if keyword.arg is None:
            continue
        name = _ALIASES.get(keyword.arg, keyword.arg)
        if name not in _CONSTRAINT_KEYS:
            continue
        value = literal_value(keyword.value)
        if value is not UNRESOLVED:
            found[name] = value
    return found


def declared_default(call: ast.Call | None) -> DefaultInfo:
    """호출에서 기본값 선언을 읽는다.

    Field(min_length=8)        → 기본값 없음 (필수)
    Field(...)                 → Ellipsis 는 "명시적 필수"
    Field(default="a")         → 기본값 있음
    Field("a", min_length=1)   → 첫 위치 인자가 기본값
    Field(default_factory=list)→ 기본값 있음 (값은 정적으로 알 수 없다)
    """
    if call is None:
        return DefaultInfo()

    factory = keyword_of(call, "default_factory")
    if factory is not None:
        return DefaultInfo(has_default=True, factory=attribute_or_name(factory))

    node = argument_of(call, 0, "default")
    if node is None:
        return DefaultInfo()

    value = literal_value(node)
    if value is Ellipsis:
        return DefaultInfo()
    if value is UNRESOLVED:
        return DefaultInfo(has_default=True)
    return DefaultInfo(has_default=True, value=value)


def marker_name(node: ast.expr | None) -> str | None:
    """호출이면 그 함수 이름을 준다. `Query(...)` → "Query"."""
    return attribute_or_name(node.func) if isinstance(node, ast.Call) else None


def find_marker(
    default: ast.expr | None, metadata: list[ast.expr], names: set[str]
) -> ast.Call | None:
    """기본값 자리와 `Annotated` 메타데이터 양쪽에서 마커를 찾는다.

    두 문법이 모두 쓰인다.

        q: str = Query(min_length=3)
        q: Annotated[str, Query(min_length=3)]
    """
    if marker_name(default) in names:
        return default  # type: ignore[return-value]
    for item in metadata:
        if marker_name(item) in names:
            return item  # type: ignore[return-value]
    return None
