"""Pass 1 의 결과물을 하나로 묶은 프로젝트 전역 인덱스.

Pass 2(추출기)는 파일을 다시 읽거나 다시 파싱하지 않는다. 필요한 건 전부
여기에 조회 API 로 노출한다. 그래서 크로스 파일 해석이 추출기 입장에서는
그냥 딕셔너리 조회 한 번이 된다.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from testweaver.analyzer.ast_utils import (
    AnnotationInfo,
    attribute_or_name,
    unwrap_annotation,
)
from testweaver.analyzer.index.constants import (
    index_constants,
    index_instances,
    index_type_aliases,
)
from testweaver.analyzer.index.file_index import ModuleInfo, collect_modules
from testweaver.analyzer.index.handler_map import index_exception_handlers
from testweaver.analyzer.index.import_map import ImportMap, build_import_map
from testweaver.analyzer.index.router_graph import (
    RouterDef,
    RouterGraph,
    build_router_graph,
)
from testweaver.analyzer.index.symbol_index import (
    ClassDef,
    FunctionDef,
    index_classes,
    index_functions,
)
from testweaver.analyzer.models import AnalysisNote, NoteCode, NoteLevel, SymbolRef

_PYDANTIC_ROOT = "BaseModel"

#: 상속 사슬을 따라갈 때의 안전장치. 이보다 깊은 모델 계층은 실무에 없다.
_MAX_BASE_DEPTH = 20

#: 타입 별칭이 다시 별칭을 가리키는 깊이 제한.
_MAX_ALIAS_DEPTH = 5


@dataclass(slots=True)
class ProjectIndex:
    root: Path
    modules: dict[Path, ModuleInfo] = field(default_factory=dict)
    imports: dict[Path, ImportMap] = field(default_factory=dict)
    classes: dict[str, ClassDef] = field(default_factory=dict)
    classes_by_name: dict[str, list[ClassDef]] = field(default_factory=dict)
    functions: dict[str, FunctionDef] = field(default_factory=dict)
    functions_by_name: dict[str, list[FunctionDef]] = field(default_factory=dict)
    constants: dict[str, Any] = field(default_factory=dict)
    instances: dict[str, str] = field(default_factory=dict)
    type_aliases: dict[str, ast.expr] = field(default_factory=dict)
    routers: RouterGraph = field(default_factory=RouterGraph)
    exception_status: dict[SymbolRef, int] = field(default_factory=dict)
    notes: list[AnalysisNote] = field(default_factory=list)

    # ─────────────── 이름 해석 ───────────────

    def resolve(self, from_file: Path, name: str) -> SymbolRef:
        """어떤 파일에서 쓰인 이름 하나를 심볼로 바꾼다.

        import 된 이름이면 원본 모듈까지, 아니면 그 파일 자신에 정의된
        것으로 본다.
        """
        imports = self.imports.get(from_file)
        if imports is not None:
            imported = imports.resolve(name)
            if imported is not None:
                return imported
        module = self.modules.get(from_file)
        return SymbolRef(
            name=name,
            module=module.module_path if module else None,
            file=from_file,
        )

    def resolve_expr(self, from_file: Path, node: ast.expr | None) -> SymbolRef | None:
        """식이 가리키는 심볼. `svc.authenticate` 같은 점 표기도 처리한다."""
        if isinstance(node, ast.Name):
            return self.resolve(from_file, node.id)
        if isinstance(node, ast.Attribute):
            base = attribute_or_name(node.value)
            imports = self.imports.get(from_file)
            if base and imports is not None:
                through_alias = imports.resolve_attribute(base, node.attr)
                if through_alias is not None:
                    return through_alias
            return SymbolRef(name=node.attr)
        return None

    # ─────────────── 심볼 조회 ───────────────

    def find_class(self, ref: SymbolRef | None) -> ClassDef | None:
        if ref is None:
            return None
        if ref.module:
            found = self.classes.get(f"{ref.module}.{ref.name}")
            if found is not None:
                return found
        return self._unique(self.classes_by_name.get(ref.name, []), ref)

    def find_function(self, ref: SymbolRef | None) -> FunctionDef | None:
        if ref is None:
            return None
        if ref.module:
            found = self.functions.get(f"{ref.module}.{ref.name}")
            if found is not None:
                return found
        return self._unique(self.functions_by_name.get(ref.name, []), ref)

    def _unique(self, candidates: list, ref: SymbolRef):
        """이름만으로 찾을 때는 후보가 유일할 때만 채택한다.

        여럿이면 엉뚱한 것을 집어 오느니 실패하고 노트를 남기는 편이 낫다.
        """
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            self.note(
                NoteLevel.WARNING,
                NoteCode.AMBIGUOUS_MODEL,
                f"{ref.name} 후보가 {len(candidates)}개라 특정하지 못했습니다",
            )
        return None

    def find_callable(self, ref: SymbolRef | None) -> FunctionDef | None:
        """호출 가능한 대상을 찾는다. 함수가 아니어도 된다.

        `throttle = RateLimiter(limit=10)` 처럼 인스턴스를 의존성으로 넘기는
        형태가 흔하다. 이때 실제로 실행되는 건 그 클래스의 `__call__` 이고,
        파라미터 선언도 거기 있다. 변수 → 클래스 → __call__ 로 되짚는다.
        """
        direct = self.find_function(ref)
        if direct is not None:
            return direct
        if ref is None:
            return None

        class_name = self.instances.get(
            f"{ref.module}.{ref.name}" if ref.module else ref.name
        )
        if class_name is None:
            return None

        # 클래스 이름은 **인스턴스를 선언한 모듈** 기준으로 해석해야 한다.
        # 클래스가 다른 파일에 있으면 그 모듈의 import 를 타야 찾을 수 있고,
        # 이름만으로 찾으면 같은 이름의 다른 클래스를 집어 온다.
        declaring = self.module_for(ref.module)
        owner = self.find_class(
            self.resolve(declaring.path, class_name)
            if declaring
            else SymbolRef(class_name, ref.module)
        )
        if owner is None:
            return None
        for statement in owner.node.body:
            if (
                isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef)
                and statement.name == "__call__"
            ):
                return FunctionDef(name=ref.name, node=statement, module=owner.module)
        return None

    def annotation(self, from_file: Path, node: ast.expr | None) -> AnnotationInfo:
        """어노테이션을 풀되, 타입 별칭이면 그 정의까지 따라간다.

        `ctx: CommonDep` 만 보면 그냥 이름 하나다. 별칭을 펼쳐야 그 안의
        `Depends(...)` 와 제약이 드러난다.
        """
        info = unwrap_annotation(node)
        return self._expand_alias(from_file, info, depth=0)

    def _expand_alias(
        self, from_file: Path, info: AnnotationInfo, depth: int
    ) -> AnnotationInfo:
        if info.base_name is None or depth > _MAX_ALIAS_DEPTH:
            return info
        ref = self.resolve(from_file, info.base_name)
        alias = self.type_aliases.get(
            f"{ref.module}.{ref.name}" if ref.module else ref.name
        )
        if alias is None:
            return info

        declaring = self.module_for(ref.module)
        expanded = self._expand_alias(
            declaring.path if declaring else from_file,
            unwrap_annotation(alias),
            depth + 1,
        )
        # 바깥에서 덧붙인 메타데이터와 optional 여부는 유지한다.
        expanded.metadata = [*expanded.metadata, *info.metadata]
        expanded.is_optional = expanded.is_optional or info.is_optional
        return expanded

    def module_for(self, module_path: str | None) -> ModuleInfo | None:
        """점 표기 모듈 경로로 모듈을 찾는다."""
        if not module_path:
            return None
        for module in self.modules.values():
            if module.module_path == module_path:
                return module
        return None

    def is_in_project(self, ref: SymbolRef | None) -> bool:
        """프로젝트가 정의한 심볼인지. 아니면 서드파티다."""
        if ref is None:
            return False
        if self.find_class(ref) is not None or self.find_function(ref) is not None:
            return True
        key = f"{ref.module}.{ref.name}" if ref.module else ref.name
        return key in self.instances or key in self.constants

    # ─────────────── 모델 ───────────────

    def is_pydantic_model(self, ref: SymbolRef | None) -> bool:
        """상속 사슬을 따라 `BaseModel` 에 닿는지 확인한다.

        `class SignupRequest(UserBase)` 처럼 부모가 다른 파일에 있어도,
        부모의 import 표를 다시 타고 올라가므로 정확히 판정된다.
        """
        return self._reaches_base_model(ref, set(), 0)

    def _reaches_base_model(
        self, ref: SymbolRef | None, seen: set[SymbolRef], depth: int
    ) -> bool:
        if ref is None or ref in seen or depth > _MAX_BASE_DEPTH:
            return False
        seen.add(ref)

        found = self.find_class(ref)
        if found is None:
            return False
        if _PYDANTIC_ROOT in found.base_names:
            return True
        return any(
            self._reaches_base_model(
                self.resolve(found.module.path, base), seen, depth + 1
            )
            for base in found.base_names
        )

    def class_mro(self, ref: SymbolRef | None) -> list[ClassDef]:
        """자기 자신부터 조상까지, 가까운 순서로.

        필드 제약을 모을 때 이 순서대로 훑고 **먼저 나온 것을 우선**하면
        자식의 재정의가 부모를 덮는다.
        """
        ordered: list[ClassDef] = []
        seen: set[SymbolRef] = set()
        self._walk_bases(ref, seen, ordered, 0)
        return ordered

    def _walk_bases(
        self,
        ref: SymbolRef | None,
        seen: set[SymbolRef],
        ordered: list[ClassDef],
        depth: int,
    ) -> None:
        if ref is None or ref in seen or depth > _MAX_BASE_DEPTH:
            return
        seen.add(ref)
        found = self.find_class(ref)
        if found is None:
            return
        ordered.append(found)
        for base in found.base_names:
            self._walk_bases(
                self.resolve(found.module.path, base), seen, ordered, depth + 1
            )

    def enum_values(self, ref: SymbolRef | None) -> list[Any] | None:
        found = self.find_class(ref)
        return found.enum_values if found and found.is_enum else None

    # ─────────────── 라우터 · 예외 ───────────────

    def router_for(self, file: Path, var_name: str) -> RouterDef | None:
        module = self.modules.get(file)
        if module is None:
            return None
        return self.routers.get(module.module_path, var_name)

    def status_for_exception(self, ref: SymbolRef | None) -> int | None:
        return self.exception_status.get(ref) if ref is not None else None

    # ─────────────── 노트 ───────────────

    def note(
        self,
        level: NoteLevel,
        code: NoteCode,
        message: str,
        file: str = "",
        line: int = 0,
    ) -> None:
        self.notes.append(AnalysisNote(level, code, message, file, line))


def build_index(
    root: Path, exclude_patterns: tuple[str, ...] | list[str] | None = None
) -> ProjectIndex:
    """Pass 0 + Pass 1 을 순서대로 실행해 인덱스를 완성한다.

    각 단계는 앞 단계의 결과만 쓰고 뒤를 보지 않는다. 그래서 파일을 어떤
    순서로 읽든 결과가 같다.
    """
    index = ProjectIndex(root=root)

    index.modules = collect_modules(root, exclude_patterns, index.notes)
    index.imports = {
        module.path: build_import_map(module) for module in index.modules.values()
    }
    index.classes, index.classes_by_name = index_classes(index.modules)
    index.functions, index.functions_by_name = index_functions(index.modules)
    index.constants = index_constants(index.modules)
    index.instances = index_instances(index.modules)
    index.type_aliases = index_type_aliases(index.modules)
    index.routers = build_router_graph(
        index.modules, index.imports, index.constants, index.notes
    )
    index.exception_status = index_exception_handlers(
        index.modules, index.imports, index.notes
    )
    return index
