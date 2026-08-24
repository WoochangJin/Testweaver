"""프로젝트가 정의하는 클래스와 함수의 위치 표.

Pass 1 의 원칙대로 여기서는 **판정하지 않는다**. `class LoginRequest(UserBase)`
가 Pydantic 모델인지는 `UserBase` 를 따라가 봐야 알 수 있는데, 그 부모가
아직 인덱싱되지 않았을 수 있다. 그래서 부모 이름만 적어 두고 판정은
인덱스가 완성된 뒤(`ProjectIndex.is_pydantic_model`)로 미룬다.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any

from testweaver.analyzer.ast_utils import UNRESOLVED, attribute_or_name, literal_value
from testweaver.analyzer.index.file_index import ModuleInfo

#: 이 중 하나를 상속하면 열거형으로 본다.
_ENUM_BASES = {"Enum", "StrEnum", "IntEnum", "Flag", "IntFlag", "ReprEnum"}


@dataclass(slots=True)
class ClassDef:
    """모듈에 정의된 클래스 하나.

    Pydantic 모델 후보만 걸러 담지 않고 전부 담는다. 무엇이 모델인지는
    상속 사슬을 따라가야 알 수 있고, 그건 Pass 2 의 일이다.
    """

    name: str
    node: ast.ClassDef
    module: ModuleInfo
    base_names: list[str] = field(default_factory=list)
    enum_values: list[Any] | None = None

    @property
    def qualified_name(self) -> str:
        return (
            f"{self.module.module_path}.{self.name}"
            if self.module.module_path
            else self.name
        )

    @property
    def is_enum(self) -> bool:
        return bool(_ENUM_BASES & set(self.base_names))


@dataclass(slots=True)
class FunctionDef:
    """모듈 최상위에 정의된 함수 하나.

    호출 그래프를 따라 예외를 수집할 때, 그리고 의존성 대상 함수를 찾을 때
    쓴다. 중첩 함수와 메서드는 담지 않는다 — 이름이 겹쳐 키가 무너지고,
    라우트 핸들러와 서비스 함수는 거의 항상 최상위에 있다.
    """

    name: str
    node: ast.FunctionDef | ast.AsyncFunctionDef
    module: ModuleInfo

    @property
    def qualified_name(self) -> str:
        return (
            f"{self.module.module_path}.{self.name}"
            if self.module.module_path
            else self.name
        )


def index_classes(
    modules: dict[Any, ModuleInfo],
) -> tuple[dict[str, ClassDef], dict[str, list[ClassDef]]]:
    """모든 클래스를 완전 이름과 단순 이름 두 갈래로 색인한다.

    단순 이름 색인은 import 문을 해석하지 못했을 때의 대비책이다.
    같은 이름이 여러 개면 후보를 모두 담아 두고, 조회 시점에 유일할 때만
    쓰도록 한다 (그렇지 않으면 엉뚱한 모델을 집어 온다).
    """
    by_qualified: dict[str, ClassDef] = {}
    by_name: dict[str, list[ClassDef]] = {}

    for module in modules.values():
        for node in module.tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            entry = ClassDef(
                name=node.name,
                node=node,
                module=module,
                base_names=_base_names(node),
            )
            if entry.is_enum:
                entry.enum_values = _enum_values(node)
            by_qualified[entry.qualified_name] = entry
            by_name.setdefault(entry.name, []).append(entry)

    return by_qualified, by_name


def index_functions(
    modules: dict[Any, ModuleInfo],
) -> tuple[dict[str, FunctionDef], dict[str, list[FunctionDef]]]:
    """모듈 최상위 함수를 완전 이름과 단순 이름으로 색인한다."""
    by_qualified: dict[str, FunctionDef] = {}
    by_name: dict[str, list[FunctionDef]] = {}

    for module in modules.values():
        for node in module.tree.body:
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            entry = FunctionDef(name=node.name, node=node, module=module)
            by_qualified[entry.qualified_name] = entry
            by_name.setdefault(entry.name, []).append(entry)

    return by_qualified, by_name


def _base_names(node: ast.ClassDef) -> list[str]:
    """상속 목록의 이름만 뽑는다. `pydantic.BaseModel` 은 "BaseModel" 이 된다.

    제네릭 기반(`Generic[T]`)은 Subscript 라 이름이 나오지 않으므로 건너뛴다.
    """
    names = []
    for base in node.bases:
        name = attribute_or_name(base)
        if name:
            names.append(name)
    return names


def _enum_values(node: ast.ClassDef) -> list[Any]:
    """열거형 멤버의 값. `allowed_values` 의 원천이 된다.

    멤버 이름이 아니라 값을 담는다. 요청 본문에 실려 가는 건 값이기 때문이다.
    (`Role.ADMIN` 이 아니라 `"admin"`)
    """
    values: list[Any] = []
    for statement in node.body:
        if not isinstance(statement, ast.Assign):
            continue
        if not all(isinstance(target, ast.Name) for target in statement.targets):
            continue
        if any(target.id.startswith("_") for target in statement.targets):  # type: ignore[union-attr]
            continue
        value = literal_value(statement.value)
        if value is not UNRESOLVED:
            values.append(value)
    return values
