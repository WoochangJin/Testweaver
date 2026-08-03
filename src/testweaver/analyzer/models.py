"""
분석 결과를 담을 model

rule에서 활용하기 위한 class 구조를 정의함.
framework adapter가 source AST를 읽고 이 타입들로 변형함.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


@dataclass
class Constraint:
    # 요청 body의 필드 이름, 타입, required 여부, min/max length, pattern 등
    # 어떠한 필드의 입력 규칙을 담음
    field_name: str
    type_name: str
    required: bool = True
    min_length: int | None = None
    max_length: int | None = None
    ge: float | None = None
    le: float | None = None
    pattern: str | None = None
    allowed_values: list[str] | None = None


@dataclass
class DependencyNode:
    # FastApi가 Depends를 통해 주입하는 의존성의 이름, 소스 코드 위치, 인증 여부, 오버라이드 가능 여부

    name: str
    source: str
    is_auth: bool = False
    overridable: bool = True


@dataclass
class ExceptionFlow:
    # 이 API가 낼 수 있는 에러 하나. handler 안의 raise 한 줄을 그대로 담는다.

    exception_type: str
    status_code: int | None = None
    error_code: str | None = None
    raised_in: str = ""


@dataclass
class Endpoint:
    # FastApi의 router decorator를 통해 정의된 하나의 endpoint를 나타냄.
    """
    어떤 경로/HTTP method에 대해 어떤 handler가 호출되는지, 
    그 handler가 어떤 request/response model을 사용하는지, 
    어떤 의존성을 주입받는지, 
    어떤 exception을 낼 수 있는지,
    인증이 필요한지, 외부 API를 호출하는지 등을 담는다.

    """
    path: str
    method: HttpMethod
    handler_name: str
    request_model: str | None = None
    response_model: str | None = None
    dependencies: list[DependencyNode] = field(default_factory=list)
    exceptions: list[ExceptionFlow] = field(default_factory=list)
    requires_auth: bool = False
    calls_external: list[str] = field(default_factory=list)


@dataclass
class Feature:
    """A full testable unit: an endpoint plus its resolved constraints.

    This is the artifact that `case_generator` consumes to derive the
    normal/failure/boundary/security case matrix.
    """
    # 테스트 대상 하나. 분석의 최종 결과물.
    # Ednpoint와 그 endpoint에 적용되는 constraints를 묶어서 하나의 feature로 정의함.
    name: str
    endpoint: Endpoint
    constraints: list[Constraint] = field(default_factory=list)
