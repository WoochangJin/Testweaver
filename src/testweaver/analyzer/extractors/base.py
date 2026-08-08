"""추출기가 공유하는 문맥과 실행 규약.

추출기를 손으로 순서 맞춰 호출하지 않는 이유는 두 가지다.

  · 순서 제약이 코드 줄 순서로만 표현되면 언젠가 깨진다. 인증 판정은
    의존성 수집 뒤여야 하는데, 그 사실이 어디에도 적혀 있지 않게 된다.
  · 추출기를 추가할 때마다 조립부를 고쳐야 하면 여러 명이 같은 파일에서
    계속 충돌한다.

`requires` 에 선언해 두면 파이프라인이 위상정렬로 순서를 정한다.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from graphlib import TopologicalSorter
from typing import Protocol, runtime_checkable

from testweaver.analyzer.index.context import ProjectIndex
from testweaver.analyzer.index.file_index import ModuleInfo
from testweaver.analyzer.index.router_graph import RouterDef
from testweaver.analyzer.models import (
    AnalysisNote,
    Constraint,
    Endpoint,
    HttpMethod,
    NoteCode,
    NoteLevel,
)


@dataclass(slots=True)
class ExtractionContext:
    """엔드포인트 하나를 추출하는 동안의 작업 공간.

    `endpoint` 와 `constraints` 는 추출기들이 차례로 채워 나간다.
    """

    index: ProjectIndex
    module: ModuleInfo
    handler: ast.FunctionDef | ast.AsyncFunctionDef
    decorator: ast.Call
    method: HttpMethod
    router: RouterDef | None
    endpoint: Endpoint
    constraints: list[Constraint] = field(default_factory=list)
    notes: list[AnalysisNote] = field(default_factory=list)

    def note(
        self, level: NoteLevel, code: NoteCode, message: str, line: int = 0
    ) -> None:
        self.notes.append(
            AnalysisNote(
                level, code, message, str(self.module.path), line or self.handler.lineno
            )
        )

    def resolve(self, name: str):
        """이 핸들러가 있는 파일 기준으로 이름을 해석한다."""
        return self.index.resolve(self.module.path, name)

    def resolve_expr(self, node: ast.expr | None):
        return self.index.resolve_expr(self.module.path, node)


@runtime_checkable
class EndpointExtractor(Protocol):
    """추출기 하나. 문맥을 받아 제자리에서 채운다."""

    name: str
    requires: tuple[str, ...]

    def extract(self, context: ExtractionContext) -> None: ...


def run_extractors(
    context: ExtractionContext, extractors: list[EndpointExtractor]
) -> None:
    """`requires` 를 만족하는 순서로 추출기를 실행한다."""
    for extractor in order_extractors(extractors):
        extractor.extract(context)


def order_extractors(extractors: list[EndpointExtractor]) -> list[EndpointExtractor]:
    """선언된 의존 관계를 위상정렬한다.

    목록에 없는 이름을 요구하면 그 제약은 무시한다. 추출기를 골라서
    실행하는 경우(테스트 등)를 막지 않기 위해서다.
    """
    available = {extractor.name for extractor in extractors}
    sorter: TopologicalSorter[str] = TopologicalSorter(
        {
            extractor.name: {r for r in extractor.requires if r in available}
            for extractor in extractors
        }
    )
    by_name = {extractor.name: extractor for extractor in extractors}
    return [by_name[name] for name in sorter.static_order()]
