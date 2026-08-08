"""테스트를 불안정하게 만드는 요소를 표시한다.

두 가지를 본다.

  · 외부 호출 — DB 세션, HTTP 클라이언트. 픽스처나 목이 없으면 테스트가
    실제 자원을 건드린다.
  · 비결정성 — `datetime.now()`, `uuid4()`, `random`. 같은 입력에 같은
    출력이 나오지 않아 응답을 그대로 단언할 수 없다.

값을 만들어 내는 건 이 단계의 일이 아니다. "여기에 준비가 필요하다"는
사실만 남긴다.
"""

from __future__ import annotations

import ast

from testweaver.analyzer.ast_utils import attribute_or_name
from testweaver.analyzer.extractors.base import ExtractionContext

#: 이 이름의 객체를 통해 호출하면 외부 자원으로 본다.
_EXTERNAL_RECEIVERS = {
    "db",
    "session",
    "conn",
    "connection",
    "cursor",
    "engine",
    "requests",
    "httpx",
    "client",
    "boto3",
    "redis",
    "cache",
    "s3",
    "kafka",
}

#: 이 타입이 붙은 인자를 통한 호출도 외부 자원이다.
_EXTERNAL_TYPES = {
    "Session",
    "AsyncSession",
    "Connection",
    "AsyncConnection",
    "Client",
    "AsyncClient",
    "Redis",
}

#: 호출할 때마다 결과가 달라지는 것들. (수신자, 속성) 또는 단일 이름.
_NONDETERMINISTIC_ATTRIBUTES = {
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("datetime", "today"),
    ("date", "today"),
    ("time", "time"),
    ("random", "random"),
    ("random", "randint"),
    ("random", "choice"),
    ("os", "urandom"),
    ("secrets", "token_hex"),
    ("secrets", "token_urlsafe"),
}
_NONDETERMINISTIC_NAMES = {"uuid1", "uuid4", "token_hex", "token_urlsafe"}


class EffectExtractor:
    """외부 호출과 비결정성을 표시한다."""

    name = "effects"
    requires: tuple[str, ...] = ()

    def extract(self, context: ExtractionContext) -> None:
        external: set[str] = set()
        nondeterministic: set[str] = set()

        typed = _externally_typed_args(context)

        for node in ast.walk(context.handler):
            if not isinstance(node, ast.Call):
                continue

            if isinstance(node.func, ast.Attribute):
                receiver = attribute_or_name(node.func.value)
                if receiver is None:
                    continue
                if receiver in _EXTERNAL_RECEIVERS or receiver in typed:
                    external.add(f"{receiver}.{node.func.attr}")
                if (receiver, node.func.attr) in _NONDETERMINISTIC_ATTRIBUTES:
                    nondeterministic.add(f"{receiver}.{node.func.attr}")

            elif isinstance(node.func, ast.Name):
                if node.func.id in _NONDETERMINISTIC_NAMES:
                    nondeterministic.add(node.func.id)

        context.endpoint.calls_external = sorted(external)
        context.endpoint.nondeterministic = sorted(nondeterministic)


def _externally_typed_args(context: ExtractionContext) -> set[str]:
    """`db: Annotated[Session, Depends(get_db)]` 처럼 타입으로 드러나는 경우.

    이름 규칙만으로는 `async_session` 같은 변형을 놓친다.
    """
    from testweaver.analyzer.ast_utils import iter_all_args, unwrap_annotation

    names: set[str] = set()
    for arg, _ in iter_all_args(context.handler):
        info = unwrap_annotation(arg.annotation)
        if info.base_name in _EXTERNAL_TYPES:
            names.add(arg.arg)
    return names
