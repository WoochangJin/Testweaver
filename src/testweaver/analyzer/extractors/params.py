"""핸들러 시그니처에서 path/query/header/cookie/form 파라미터를 읽는다.

`GET /orders/{order_id}?limit=20` 같은 요청은 본문이 없다. 이 파라미터들을
버리면 GET 계열 엔드포인트의 테스트는 만들 수가 없다 — 경계값을 어디에
넣어야 하는지 알 수 없기 때문이다.

본문 모델은 여기서 `request_model` 로 지목만 하고, 필드 제약을 푸는 건
`body` 추출기가 이어받는다.
"""

from __future__ import annotations

import ast
import re

from testweaver.analyzer.ast_utils import (
    UNRESOLVED,
    iter_all_args,
    keyword_of,
    literal_value,
    unwrap_annotation,
)
from testweaver.analyzer.extractors.base import ExtractionContext
from testweaver.analyzer.extractors.fields import (
    DEPENDENCY_MARKERS,
    FRAMEWORK_TYPES,
    PARAM_MARKERS,
    DefaultInfo,
    declared_default,
    field_constraints,
    find_marker,
    marker_name,
)
from testweaver.analyzer.models import Constraint, NoteCode, NoteLevel, ParamLocation

_MARKER_LOCATIONS = {
    "Path": ParamLocation.PATH,
    "Query": ParamLocation.QUERY,
    "Header": ParamLocation.HEADER,
    "Cookie": ParamLocation.COOKIE,
    "Body": ParamLocation.BODY,
    "Form": ParamLocation.FORM,
    "File": ParamLocation.FORM,
}

#: 경로 템플릿의 이름. `{order_id}` 와 `{path:path}` 를 모두 잡는다.
_PATH_TEMPLATE = re.compile(r"\{([^:}]+)")

#: 업로드 파일은 본문이지만 multipart 라 따로 본다.
_FILE_TYPES = {"UploadFile"}


class ParamExtractor:
    """FastAPI 의 파라미터 판정 규칙을 그대로 따라간다. 순서가 곧 규칙이다."""

    name = "params"
    requires = ("route", "dependency")

    def extract(self, context: ExtractionContext) -> None:
        path_names = set(_PATH_TEMPLATE.findall(context.endpoint.path))
        claimed: set[str] = set()

        self._read_signature(
            context, context.handler, context.module.path, path_names, claimed
        )
        self._read_dependency_signatures(context, path_names, claimed)

    def _read_signature(
        self,
        context: ExtractionContext,
        function,
        origin_file,
        path_names: set[str],
        claimed: set[str],
    ) -> None:
        for arg, default in iter_all_args(function):
            if arg.arg in {"self", "cls"} or arg.arg in claimed:
                continue

            info = unwrap_annotation(arg.annotation)

            # 의존성은 `dependency` 추출기의 몫이다.
            if find_marker(default, info.metadata, DEPENDENCY_MARKERS) is not None:
                continue
            # 프레임워크가 채워 넣는 자리는 입력이 아니다.
            if info.base_name in FRAMEWORK_TYPES:
                continue

            marker = find_marker(default, info.metadata, PARAM_MARKERS)
            location = self._location(
                context, arg.arg, info, marker, path_names, origin_file
            )
            if location is None:
                continue  # 본문 모델. request_model 로 이미 지목했다.

            claimed.add(arg.arg)
            context.constraints.append(
                self._constraint(
                    context,
                    wire_name(arg.arg, marker, location),
                    info,
                    marker,
                    default,
                    location,
                    origin_file,
                )
            )

    def _read_dependency_signatures(
        self, context: ExtractionContext, path_names: set[str], claimed: set[str]
    ) -> None:
        """의존성 함수가 선언한 파라미터도 이 엔드포인트의 입력이다.

        FastAPI 는 의존성의 Header/Query/Cookie 인자를 엔드포인트 스펙으로
        끌어올린다. 인증 의존성이 `Authorization` 헤더를 받는 경우가 대표적인데,
        핸들러 시그니처에는 그 이름이 전혀 나타나지 않는다.
        """
        for dependency in context.endpoint.dependencies:
            # 함수가 아니라 호출 가능한 클래스 인스턴스일 수도 있다.
            target = context.index.find_callable(dependency.source)
            if target is None:
                continue
            self._read_signature(
                context, target.node, target.module.path, path_names, claimed
            )

    # ─────────────── 위치 판정 ───────────────

    def _location(
        self,
        context: ExtractionContext,
        name: str,
        info,
        marker: ast.Call | None,
        path_names: set[str],
        origin_file,
    ) -> ParamLocation | None:
        """FastAPI 가 파라미터 위치를 정하는 순서를 그대로 따른다."""
        if marker is not None:
            return _MARKER_LOCATIONS.get(marker_name(marker), ParamLocation.QUERY)

        if name in path_names:
            return ParamLocation.PATH

        if info.base_name in _FILE_TYPES or info.item_name in _FILE_TYPES:
            return ParamLocation.FORM

        # 프로젝트가 정의한 Pydantic 모델이면 요청 본문이다.
        model = (
            context.index.resolve(origin_file, info.model_name)
            if info.model_name
            else None
        )
        if model is not None and context.index.is_pydantic_model(model):
            self._claim_body(context, model)
            return None

        # 남은 스칼라는 쿼리 파라미터다 (FastAPI 기본 규칙).
        return ParamLocation.QUERY

    def _claim_body(self, context: ExtractionContext, model) -> None:
        if context.endpoint.request_model is None:
            context.endpoint.request_model = model
            return
        if context.endpoint.request_model != model:
            context.note(
                NoteLevel.INFO,
                NoteCode.UNSUPPORTED_SYNTAX,
                f"본문 모델이 여럿입니다. {context.endpoint.request_model} 만 씁니다",
            )

    # ─────────────── 제약 ───────────────

    def _constraint(
        self,
        context: ExtractionContext,
        name: str,
        info,
        marker: ast.Call | None,
        default: ast.expr | None,
        location: ParamLocation,
        origin_file,
    ) -> Constraint:
        declared = _resolve_default(marker, default)
        required = location is ParamLocation.PATH or not declared.has_default
        return Constraint(
            field_name=name,
            type_name=_type_name(info),
            required=required,
            location=location,
            nullable=info.is_optional,
            default=declared.value,
            default_factory=declared.factory,
            allowed_values=self._allowed_values(context, info, origin_file),
            **field_constraints(marker),
        )

    def _allowed_values(self, context: ExtractionContext, info, origin_file):
        """타입은 그 인자를 선언한 모듈 기준으로 해석한다.

        의존성 함수의 인자는 핸들러와 다른 파일에 있으므로, 핸들러 기준으로
        찾으면 모듈이 틀린다.
        """
        if info.literal_values:
            return list(info.literal_values)
        if info.model_name:
            return context.index.enum_values(
                context.index.resolve(origin_file, info.model_name)
            )
        return None


def wire_name(arg_name: str, marker: ast.Call | None, location: ParamLocation) -> str:
    """요청에 실제로 실려 나가는 이름.

    파이썬 인자 이름과 전송 이름은 다를 수 있다.

        x_api_key: Annotated[str, Header()]        →  "x-api-key"
        q: Annotated[str, Query(alias="search")]   →  "search"

    헤더는 밑줄을 하이픈으로 바꾸는 게 FastAPI 기본값이다(`convert_underscores`).
    인자 이름을 그대로 쓰면 생성된 테스트가 엉뚱한 헤더를 보내 인증에 실패한다.
    """
    alias = (
        literal_value(keyword_of(marker, "alias")) if marker is not None else UNRESOLVED
    )
    if isinstance(alias, str):
        return alias

    if location is not ParamLocation.HEADER:
        return arg_name

    convert = (
        literal_value(keyword_of(marker, "convert_underscores"))
        if marker
        else UNRESOLVED
    )
    if convert is False:
        return arg_name
    return arg_name.replace("_", "-")


def _resolve_default(marker: ast.Call | None, default: ast.expr | None) -> DefaultInfo:
    """마커와 인자 양쪽에서 기본값을 찾는다. 두 문법이 섞여 쓰이기 때문이다.

    q: str = Query(min_length=3)              마커가 기본값 자리를 차지 → 필수
    q: str = Query(default=None)              마커 안에 기본값
    limit: Annotated[int, Query(ge=1)] = 20   기본값은 인자 쪽에
    sort: Literal["asc", "desc"] = "asc"      마커 없이 인자 쪽에
    """
    from_marker = declared_default(marker)
    if from_marker.has_default:
        return from_marker

    # 인자의 기본값이 마커 호출 자체라면 그건 기본값이 아니다.
    if default is None or default is marker:
        return DefaultInfo()

    value = literal_value(default)
    if value is UNRESOLVED:
        return DefaultInfo(has_default=True)
    return DefaultInfo(has_default=True, value=value)


def _type_name(info) -> str:
    if info.is_collection and info.item_name:
        return f"{info.base_name}[{info.item_name}]"
    return info.base_name or info.raw
