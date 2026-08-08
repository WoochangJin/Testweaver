"""요청 본문 Pydantic 모델을 `Constraint` 목록으로 푼다.

`required` 판정이 이 파일에서 가장 중요하다. Pydantic v2 에서 필수 여부를
가르는 건 타입이 아니라 **기본값의 유무**다.

    password: str = Field(min_length=8)   기본값이 없다 → 필수
    age: int = Field(default=20)          기본값이 있다 → 선택

`= Field(...)` 가 붙어 있다는 이유로 선택으로 보면, "필드 누락" 경계 케이스가
한 건도 생성되지 않는다.
"""

from __future__ import annotations

import ast
from typing import Any

from testweaver.analyzer.ast_utils import unwrap_annotation
from testweaver.analyzer.extractors.base import ExtractionContext
from testweaver.analyzer.extractors.fields import (
    DefaultInfo,
    declared_alias,
    declared_default,
    field_constraints,
    marker_name,
)
from testweaver.analyzer.index.symbol_index import ClassDef
from testweaver.analyzer.models import (
    Constraint,
    NoteCode,
    NoteLevel,
    ParamLocation,
    SymbolRef,
)

#: 필드가 아닌 클래스 속성들.
_NON_FIELD_NAMES = {"model_config", "Config"}
_NON_FIELD_ANNOTATIONS = {"ClassVar", "InitVar"}

#: 커스텀 검증을 선언하는 데코레이터. 값 생성까지는 못 하지만 존재는 알린다.
_VALIDATOR_DECORATORS = {"field_validator", "validator"}

#: 중첩 모델을 따라 들어가는 깊이 제한.
_MAX_NESTING = 5


class BodyExtractor:
    """`request_model` 이 지목한 모델의 필드 제약을 모은다."""

    name = "body"
    requires = ("params",)

    def extract(self, context: ExtractionContext) -> None:
        model = context.endpoint.request_model
        if model is None:
            return
        context.constraints.extend(
            collect_constraints(context, model, set(), depth=0, prefix="")
        )


def collect_constraints(
    context: ExtractionContext,
    model: SymbolRef,
    seen: set[SymbolRef],
    depth: int,
    prefix: str,
) -> list[Constraint]:
    """모델 하나의 필드를 제약으로 바꾼다. 상속과 중첩을 따라간다."""
    if model in seen or depth > _MAX_NESTING:
        return []
    branch_seen = {*seen, model}

    classes = context.index.class_mro(model)
    if not classes:
        context.note(
            NoteLevel.WARNING,
            NoteCode.MODEL_NOT_FOUND,
            f"{model} 의 정의를 찾지 못해 본문 제약을 읽을 수 없습니다",
        )
        return []

    validated = _validated_fields(classes)
    constraints: list[Constraint] = []
    claimed: set[str] = set()

    # class_mro 는 자식이 먼저다. 먼저 본 필드를 채택하면 재정의가 부모를 덮는다.
    for owner in classes:
        for statement in owner.node.body:
            field = _field_of(statement)
            if field is None:
                continue
            name, annotation, assigned = field
            if name in claimed:
                continue
            claimed.add(name)

            constraints.extend(
                _constraints_for(
                    context,
                    owner=owner,
                    name=f"{prefix}{name}",
                    annotation=annotation,
                    assigned=assigned,
                    has_validator=name in validated,
                    seen=branch_seen,
                    depth=depth,
                )
            )
    return constraints


def _constraints_for(
    context: ExtractionContext,
    owner: ClassDef,
    name: str,
    annotation: ast.expr | None,
    assigned: ast.expr | None,
    has_validator: bool,
    seen: set[SymbolRef],
    depth: int,
) -> list[Constraint]:
    info = context.index.annotation(owner.module.path, annotation)
    marker = _field_marker(assigned, info.metadata)
    declared = _resolve_default(marker, assigned)

    nested = _nested_model(context, owner, info)
    constraint = Constraint(
        field_name=_wire_name(name, marker),
        type_name=_type_name(info),
        required=not declared.has_default,
        location=ParamLocation.BODY,
        nullable=info.is_optional,
        default=declared.value,
        default_factory=declared.factory,
        allowed_values=_allowed_values(context, owner, info),
        nested_model=nested,
        has_custom_validator=has_validator,
        **field_constraints(marker),
    )

    if has_validator:
        context.note(
            NoteLevel.INFO,
            NoteCode.CUSTOM_VALIDATOR,
            f"{name} 에 커스텀 검증이 있어 제약을 완전히 표현하지 못합니다",
        )

    if nested is None:
        return [constraint]

    # 중첩 모델은 자기 자신도 남기고 내부 필드를 점 표기로 펼친다.
    return [
        constraint,
        *collect_constraints(
            context, nested, seen, depth + 1, prefix=f"{constraint.field_name}."
        ),
    ]


# ─────────────────────────── 필드 인식 ───────────────────────────


def _field_of(
    statement: ast.stmt,
) -> tuple[str, ast.expr | None, ast.expr | None] | None:
    """모델 필드 선언이면 (이름, 어노테이션, 대입값)을 준다.

    필드는 반드시 어노테이션이 붙는다. `model_config = ConfigDict(...)` 처럼
    어노테이션 없는 대입은 필드가 아니다.
    """
    if not isinstance(statement, ast.AnnAssign) or not isinstance(
        statement.target, ast.Name
    ):
        return None

    name = statement.target.id
    if name.startswith("_") or name in _NON_FIELD_NAMES:
        return None

    outer = unwrap_annotation(statement.annotation)
    if outer.base_name in _NON_FIELD_ANNOTATIONS:
        return None

    return name, statement.annotation, statement.value


def _validated_fields(classes: list[ClassDef]) -> set[str]:
    """`@field_validator("password")` 가 걸린 필드 이름을 모은다."""
    validated: set[str] = set()
    for owner in classes:
        for statement in owner.node.body:
            if not isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for decorator in statement.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if marker_name(decorator) not in _VALIDATOR_DECORATORS:
                    continue
                for argument in decorator.args:
                    if isinstance(argument, ast.Constant) and isinstance(
                        argument.value, str
                    ):
                        validated.add(argument.value)
    return validated


def _field_marker(
    assigned: ast.expr | None, metadata: list[ast.expr]
) -> ast.Call | None:
    """`Field(...)` 를 대입값과 `Annotated` 메타데이터 양쪽에서 찾는다."""
    if marker_name(assigned) == "Field":
        return assigned  # type: ignore[return-value]
    for item in metadata:
        if marker_name(item) == "Field":
            return item  # type: ignore[return-value]
    return None


def _resolve_default(marker: ast.Call | None, assigned: ast.expr | None) -> DefaultInfo:
    """기본값 유무를 판정한다. required 판정의 근거가 된다.

    x: str                              대입 없음        → 필수
    x: str = Field(min_length=8)        Field 에 기본값 없음 → 필수
    x: str = Field(...)                 Ellipsis 는 명시적 필수
    x: str = Field(default="a")         → 선택
    x: str = "a"                        → 선택
    x: Annotated[int, Field(gt=0)] = 50 기본값은 대입 쪽에 → 선택
    """
    from_marker = declared_default(marker)
    if from_marker.has_default:
        return from_marker

    if assigned is None or assigned is marker:
        return DefaultInfo()

    from testweaver.analyzer.ast_utils import UNRESOLVED, literal_value

    value = literal_value(assigned)
    if value is UNRESOLVED:
        return DefaultInfo(has_default=True)
    return DefaultInfo(has_default=True, value=value)


def _wire_name(name: str, marker: ast.Call | None) -> str:
    """별칭이 있으면 그쪽이 요청에 실려 나가는 이름이다.

    파이썬 이름을 그대로 쓰면 생성된 요청의 키가 달라 검증에 걸린다.
    중첩 필드는 앞의 경로가 이미 별칭으로 붙어 있으므로 마지막 조각만 바꾼다.
    """
    alias = declared_alias(marker)
    if alias is None:
        return name
    head, sep, _ = name.rpartition(".")
    return f"{head}{sep}{alias}" if sep else alias


# ─────────────────────────── 타입 해석 ───────────────────────────


def _resolve_in(context: ExtractionContext, owner: ClassDef, name: str) -> SymbolRef:
    """필드 타입은 **그 필드를 선언한 모듈** 기준으로 해석한다.

    핸들러가 있는 파일을 기준으로 삼으면 안 된다. `OrderCreate.items` 의
    `OrderItem` 은 schemas/order.py 에서만 import 되어 있고, 라우터 파일은
    그 이름을 모른다. 이름 하나로 우연히 찾아지더라도 모듈이 틀리면 코드
    생성 단계에서 import 문을 만들 수 없다.
    """
    return context.index.resolve(owner.module.path, name)


def _nested_model(
    context: ExtractionContext, owner: ClassDef, info
) -> SymbolRef | None:
    """필드 타입이 다시 Pydantic 모델이면 그 참조를 준다."""
    if not info.model_name:
        return None
    ref = _resolve_in(context, owner, info.model_name)
    return ref if context.index.is_pydantic_model(ref) else None


def _allowed_values(
    context: ExtractionContext, owner: ClassDef, info
) -> list[Any] | None:
    if info.literal_values:
        return list(info.literal_values)
    if info.model_name:
        return context.index.enum_values(_resolve_in(context, owner, info.model_name))
    return None


def _type_name(info) -> str:
    if info.is_collection and info.item_name:
        return f"{info.base_name}[{info.item_name}]"
    return info.base_name or info.raw
