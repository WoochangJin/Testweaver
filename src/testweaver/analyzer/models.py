"""analyzer 가 만들어 내는 자료구조.

하류 단계(케이스 매트릭스, 코드 생성)는 여기 정의된 타입만 소비한다.
따라서 이 파일은 analyzer 의 공개 계약이며, 필드를 바꾸면 하류가 영향을 받는다.

설계 원칙 두 가지:

1. 참조는 문자열이 아니라 `SymbolRef` 로 표현한다.
   "LoginRequest" 라는 이름만으로는 어느 모듈의 것인지 알 수 없고,
   그러면 코드 생성 단계에서 import 문을 만들 수 없다.

2. 해석하지 못한 지점은 `AnalysisNote` 로 남긴다.
   정적 분석은 반드시 실패하는 지점이 있다. 그걸 None 이나 빈 리스트로
   뭉개면 사용자는 "왜 케이스가 안 나왔는지" 알 수 없고, 잘못된 결과가
   조용히 흘러간다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ParamLocation(StrEnum):
    """입력 파라미터가 실려 오는 위치.

    body 든 query 든 같은 `Constraint` 타입으로 흐르게 하기 위한 구분자다.
    그래야 경계값 규칙 같은 하류 로직을 위치별로 새로 짜지 않아도 된다.
    """

    PATH = "path"
    QUERY = "query"
    HEADER = "header"
    COOKIE = "cookie"
    BODY = "body"
    FORM = "form"


class NoteLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class NoteCode(StrEnum):
    """해석 실패의 표준 분류.

    자유 문자열을 쓰면 오타가 조용히 리포트를 망가뜨리므로 열거형으로 고정한다.
    """

    PARSE_FAILED = "PARSE_FAILED"
    UNRESOLVED_PATH = "UNRESOLVED_PATH"
    UNRESOLVED_PREFIX = "UNRESOLVED_PREFIX"
    UNRESOLVED_STATUS = "UNRESOLVED_STATUS"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    AMBIGUOUS_MODEL = "AMBIGUOUS_MODEL"
    EXTERNAL_SYMBOL = "EXTERNAL_SYMBOL"
    DYNAMIC_ROUTE = "DYNAMIC_ROUTE"
    MULTI_MOUNT = "MULTI_MOUNT"
    CUSTOM_VALIDATOR = "CUSTOM_VALIDATOR"
    UNSUPPORTED_SYNTAX = "UNSUPPORTED_SYNTAX"


class DependencyOrigin(StrEnum):
    """의존성이 선언된 위치. 네 곳 모두 수집해야 인증 판정이 정확해진다."""

    HANDLER = "handler"  # 핸들러 인자의 Depends(...)
    ROUTE = "route"  # @router.get(..., dependencies=[...])
    ROUTER = "router"  # APIRouter(dependencies=[...])
    APP = "app"  # FastAPI(dependencies=[...])


@dataclass(frozen=True, slots=True)
class SymbolRef:
    """코드 상의 심볼 하나에 대한 참조.

    `module` 이 None 이면 아직 해석되지 않았거나 프로젝트 밖의 심볼이다.
    frozen 인 이유는 방문 여부를 추적하는 set 의 원소로 쓰이기 때문이다.
    """

    name: str
    module: str | None = None
    file: Path | None = None

    @property
    def is_resolved(self) -> bool:
        return self.module is not None

    def __str__(self) -> str:
        return f"{self.module}.{self.name}" if self.module else self.name


@dataclass(slots=True)
class AnalysisNote:
    """해석하지 못했거나 불완전하게 해석한 지점의 기록."""

    level: NoteLevel
    code: NoteCode
    message: str
    file: str = ""
    line: int = 0

    def __str__(self) -> str:
        where = f"{self.file}:{self.line}" if self.file else "?"
        return f"[{self.level}] {self.code} {where} — {self.message}"


@dataclass(slots=True)
class Constraint:
    """입력 값 하나에 걸린 제약.

    Pydantic 모델의 필드에서도, Query()/Path() 같은 파라미터 마커에서도
    같은 타입이 나온다. 구분은 `location` 이 한다.

    `default` 는 `required` 가 False 일 때만 의미가 있다.
    `default_factory` 는 팩토리 이름 문자열이며, 값은 정적으로 알 수 없다.
    """

    field_name: str
    type_name: str
    required: bool = True
    location: ParamLocation = ParamLocation.BODY
    nullable: bool = False

    min_length: int | None = None
    max_length: int | None = None
    ge: float | None = None
    le: float | None = None
    gt: float | None = None
    lt: float | None = None
    multiple_of: float | None = None
    pattern: str | None = None
    allowed_values: list[Any] | None = None

    default: Any = None
    default_factory: str | None = None

    nested_model: SymbolRef | None = None
    has_custom_validator: bool = False

    @property
    def is_bounded(self) -> bool:
        """경계값을 만들 수 있는 수치/길이 제약이 하나라도 있는지."""
        return any(
            value is not None
            for value in (
                self.min_length,
                self.max_length,
                self.ge,
                self.le,
                self.gt,
                self.lt,
            )
        )


@dataclass(slots=True)
class DependencyNode:
    """`Depends(...)` / `Security(...)` 주입 지점 하나."""

    name: str
    source: SymbolRef
    origin: DependencyOrigin = DependencyOrigin.HANDLER
    is_auth: bool = False
    is_permission: bool = False
    scopes: list[str] = field(default_factory=list)
    overridable: bool = True


@dataclass(slots=True)
class ExceptionFlow:
    """핸들러가 (직접 또는 간접으로) 발생시킬 수 있는 예외 하나.

    `depth` 0 은 핸들러 본문, 1 이상은 호출 그래프를 따라간 깊이다.
    `resolved` 가 False 면 예외 타입은 알아냈지만 상태코드를 확정하지 못한 것이다.
    """

    exception_type: str
    status_code: int | None = None
    error_code: str | None = None
    raised_in: str = ""
    depth: int = 0
    resolved: bool = True


@dataclass(slots=True)
class Endpoint:
    """라우트 하나. `path` 는 prefix 가 모두 합성된 완전 경로다."""

    path: str
    method: HttpMethod
    handler_name: str

    request_model: SymbolRef | None = None
    response_model: SymbolRef | None = None

    #: 성공 응답의 상태코드.
    #: status_code 인자가 없으면 FastAPI 기본값인 200 이 확정된다.
    #: 인자는 있는데 리터럴로 해석하지 못한 경우에만 None 이며, 이때는
    #: UNRESOLVED_STATUS 노트가 함께 남는다. 200 으로 뭉개면 틀린 기대값이
    #: 조용히 생성된다.
    success_status_code: int | None = 200

    dependencies: list[DependencyNode] = field(default_factory=list)
    exceptions: list[ExceptionFlow] = field(default_factory=list)
    requires_auth: bool = False
    requires_permission: bool = False

    calls_external: list[str] = field(default_factory=list)
    nondeterministic: list[str] = field(default_factory=list)

    source_file: Path | None = None
    module_path: str = ""
    lineno: int = 0
    is_async: bool = False
    tags: list[str] = field(default_factory=list)
    deprecated: bool = False


@dataclass(slots=True)
class Feature:
    """테스트 설계의 단위. 엔드포인트 하나와 그 입력 제약을 묶은 것.

    `id` 는 앱 안에서 유일하다. `name`(핸들러 이름)은 파일이 다르면 겹칠 수
    있어 식별자로 쓸 수 없다.
    """

    id: str
    name: str
    endpoint: Endpoint
    constraints: list[Constraint] = field(default_factory=list)
    notes: list[AnalysisNote] = field(default_factory=list)

    def constraints_in(self, location: ParamLocation) -> list[Constraint]:
        return [c for c in self.constraints if c.location is location]


@dataclass(slots=True)
class AnalysisResult:
    """`analyze_project()` 의 반환값.

    `notes` 에는 인덱싱 단계의 전역 노트와 기능별 노트가 모두 모인다.
    """

    features: list[Feature] = field(default_factory=list)
    notes: list[AnalysisNote] = field(default_factory=list)

    def notes_with(self, code: NoteCode) -> list[AnalysisNote]:
        return [note for note in self.notes if note.code is code]

    @property
    def has_errors(self) -> bool:
        return any(note.level is NoteLevel.ERROR for note in self.notes)
