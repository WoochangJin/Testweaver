"""모듈 안의 지역 이름을 원본 심볼로 되돌리는 표.

`routers/auth.py` 가 `LoginRequest` 를 쓸 때 그게 어느 모듈의 것인지는
그 파일의 import 문에만 적혀 있다. 이 표가 없으면 크로스 파일 해석이
전부 불가능하고, 코드 생성 단계에서 import 문도 만들 수 없다.
"""

from __future__ import annotations

import ast

from testweaver.analyzer.index.file_index import ModuleInfo
from testweaver.analyzer.models import SymbolRef


class ImportMap:
    """한 모듈의 import 문을 해석한 결과.

    두 갈래로 나눠 담는다.

        from schemas.auth import LoginRequest   → symbols["LoginRequest"]
        import services.auth_service as svc     → modules["svc"]

    앞쪽은 이름 하나를 바로 해석할 때, 뒤쪽은 `svc.authenticate` 처럼
    점 표기로 접근할 때 쓴다.
    """

    __slots__ = ("modules", "symbols")

    def __init__(
        self,
        symbols: dict[str, SymbolRef] | None = None,
        modules: dict[str, str] | None = None,
    ) -> None:
        self.symbols: dict[str, SymbolRef] = symbols or {}
        self.modules: dict[str, str] = modules or {}

    def resolve(self, name: str) -> SymbolRef | None:
        """지역 이름 하나를 심볼로. import 된 적이 없으면 None."""
        return self.symbols.get(name)

    def resolve_attribute(self, base: str, attr: str) -> SymbolRef | None:
        """`svc.authenticate` 처럼 모듈 별칭을 거쳐 접근한 심볼."""
        module = self.modules.get(base)
        if module is not None:
            return SymbolRef(name=attr, module=module)

        # `from services import auth_service` 후 `auth_service.authenticate`
        imported = self.symbols.get(base)
        if imported is not None and imported.module is not None:
            return SymbolRef(name=attr, module=f"{imported.module}.{imported.name}")
        return None


def build_import_map(module: ModuleInfo) -> ImportMap:
    """모듈 하나의 import 문을 전부 해석한다."""
    result = ImportMap()
    for node in ast.walk(module.tree):
        if isinstance(node, ast.Import):
            _read_import(node, result)
        elif isinstance(node, ast.ImportFrom):
            _read_import_from(node, module, result)
    return result


def _read_import(node: ast.Import, result: ImportMap) -> None:
    for alias in node.names:
        if alias.asname:
            #   import services.auth_service as svc  →  svc = services.auth_service
            result.modules[alias.asname] = alias.name
        else:
            #   import services.auth_service  →  최상위 이름 services 만 바인딩된다
            top = alias.name.partition(".")[0]
            result.modules[top] = top


def _read_import_from(
    node: ast.ImportFrom, module: ModuleInfo, result: ImportMap
) -> None:
    origin = (
        _resolve_relative(module.package, node.level, node.module)
        if node.level
        else (node.module or "")
    )
    for alias in node.names:
        if alias.name == "*":
            continue
        local = alias.asname or alias.name
        result.symbols[local] = SymbolRef(name=alias.name, module=origin or None)
        # `from . import svc` 처럼 가져온 것이 모듈일 수 있다. 그때는
        # `svc.DomainError` 로 접근하므로 모듈 경로로도 기억해 둔다.
        result.modules.setdefault(
            local, f"{origin}.{alias.name}" if origin else alias.name
        )


def _resolve_relative(package: str, level: int, module: str | None) -> str:
    """상대 임포트를 절대 모듈 경로로 바꾼다.

    `level` 은 점의 개수다. 한 개는 자기 패키지, 두 개는 그 부모를 뜻한다.

        routers/auth.py (package="routers")
            from .base import X      level=1  →  "routers.base"
            from ..deps import X     level=2  →  "deps"
        main.py (package="")
            from .errors import X    level=1  →  "errors"

    기준이 모듈이 아니라 **패키지**라는 점이 핵심이다. 모듈 경로를 기준으로
    잡으면 `__init__.py` 에서 한 단계씩 어긋난다.
    """
    parts = package.split(".") if package else []
    if level > 1:
        drop = level - 1
        parts = parts[:-drop] if drop <= len(parts) else []
    if module:
        parts = [*parts, *module.split(".")]
    return ".".join(parts)
