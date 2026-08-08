"""analyzer 의 진입점. Pass 0 → Pass 1 → Pass 2 를 순서대로 엮는다.

    analyze_project(project_root) -> AnalysisResult

대상 프로젝트를 실행하지 않는다. 순수 AST 정적 분석만 쓴다.
"""

from __future__ import annotations

from pathlib import Path

from testweaver.analyzer.extractors import DEFAULT_EXTRACTORS, EndpointExtractor
from testweaver.analyzer.extractors.base import ExtractionContext, order_extractors
from testweaver.analyzer.extractors.route import find_routes
from testweaver.analyzer.index.context import ProjectIndex, build_index
from testweaver.analyzer.models import AnalysisResult, Endpoint, Feature


def analyze_project(
    root: Path,
    exclude_patterns: tuple[str, ...] | list[str] | None = None,
    extractors: list[EndpointExtractor] | None = None,
) -> AnalysisResult:
    """프로젝트를 분석해 테스트 가능한 기능 목록을 만든다."""
    index = build_index(root, exclude_patterns)
    return extract_features(index, extractors)


def extract_features(
    index: ProjectIndex, extractors: list[EndpointExtractor] | None = None
) -> AnalysisResult:
    """이미 만들어진 인덱스로 Pass 2 만 수행한다.

    인덱스를 재사용하고 싶을 때, 그리고 추출기를 골라 실행하며 시험할 때
    쓴다.
    """
    ordered = order_extractors(list(extractors or DEFAULT_EXTRACTORS))
    features: list[Feature] = []

    for module in index.modules.values():
        for site in find_routes(module, index, index.notes):
            context = ExtractionContext(
                index=index,
                module=site.module,
                handler=site.handler,
                decorator=site.decorator,
                method=site.method,
                router=site.router,
                endpoint=Endpoint(
                    path="", method=site.method, handler_name=site.handler.name
                ),
            )
            for extractor in ordered:
                extractor.extract(context)

            features.append(
                Feature(
                    id=f"{site.method.value} {context.endpoint.path}",
                    name=site.handler.name,
                    endpoint=context.endpoint,
                    constraints=context.constraints,
                    notes=context.notes,
                )
            )

    features.sort(key=lambda feature: feature.id)
    return AnalysisResult(
        features=features,
        notes=[*index.notes, *(note for feature in features for note in feature.notes)],
    )
