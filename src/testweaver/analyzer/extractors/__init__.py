"""Pass 2 — 엔드포인트 하나씩을 훑으며 정보를 채우는 추출기들.

Pass 1 이 만든 `ProjectIndex` 를 조회하므로, 여기서는 파일을 다시 읽거나
파싱하지 않는다. 크로스 파일 해석이 딕셔너리 조회 한 번으로 끝난다.

추출기는 서로의 결과에 의존할 수 있고(인증 판정은 의존성 수집 뒤여야 한다),
그 순서는 각 추출기의 `requires` 에 선언한다. 실행 순서는 파이프라인이
위상정렬로 정하므로, 새 추출기를 추가할 때 다른 파일을 고칠 일이 없다.
"""

from testweaver.analyzer.extractors.auth import AuthExtractor
from testweaver.analyzer.extractors.base import (
    EndpointExtractor,
    ExtractionContext,
    order_extractors,
    run_extractors,
)
from testweaver.analyzer.extractors.body import BodyExtractor
from testweaver.analyzer.extractors.dependency import DependencyExtractor
from testweaver.analyzer.extractors.effects import EffectExtractor
from testweaver.analyzer.extractors.exception import ExceptionExtractor
from testweaver.analyzer.extractors.params import ParamExtractor
from testweaver.analyzer.extractors.route import RouteExtractor

#: 기본 실행 목록. 순서는 여기가 아니라 각 추출기의 `requires` 가 정한다.
DEFAULT_EXTRACTORS: list[EndpointExtractor] = [
    RouteExtractor(),
    ParamExtractor(),
    BodyExtractor(),
    DependencyExtractor(),
    AuthExtractor(),
    ExceptionExtractor(),
    EffectExtractor(),
]

__all__ = [
    "DEFAULT_EXTRACTORS",
    "AuthExtractor",
    "BodyExtractor",
    "DependencyExtractor",
    "EffectExtractor",
    "EndpointExtractor",
    "ExceptionExtractor",
    "ExtractionContext",
    "ParamExtractor",
    "RouteExtractor",
    "order_extractors",
    "run_extractors",
]
