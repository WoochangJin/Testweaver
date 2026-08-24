"""FastAPI 프로젝트를 정적 분석해 테스트 가능한 기능 목록을 뽑아내는 계층.

공개 계약은 `models` 의 자료구조다. 하류 단계는 이 타입들만 소비한다.
"""

from testweaver.analyzer.models import (
    AnalysisNote,
    AnalysisResult,
    Constraint,
    DependencyNode,
    DependencyOrigin,
    Endpoint,
    ExceptionFlow,
    Feature,
    HttpMethod,
    NoteCode,
    NoteLevel,
    ParamLocation,
    SymbolRef,
)

__all__ = [
    "AnalysisNote",
    "AnalysisResult",
    "Constraint",
    "DependencyNode",
    "DependencyOrigin",
    "Endpoint",
    "ExceptionFlow",
    "Feature",
    "HttpMethod",
    "NoteCode",
    "NoteLevel",
    "ParamLocation",
    "SymbolRef",
]
