"""Pass 0 — 프로젝트의 파이썬 모듈을 모아 파싱한다.

이후 모든 인덱싱과 추출은 여기서 만든 `ModuleInfo` 위에서 이뤄진다.
파일을 두 번 읽거나 두 번 파싱하는 일이 없도록, AST 는 여기서 한 번만 만든다.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from testweaver.analyzer.ast_utils import (
    iter_python_files,
    module_path_of,
    safe_parse,
)
from testweaver.analyzer.models import AnalysisNote, NoteCode, NoteLevel


@dataclass(slots=True)
class ModuleInfo:
    """파싱이 끝난 모듈 하나."""

    path: Path
    module_path: str
    tree: ast.Module
    is_package: bool = False

    @property
    def package(self) -> str:
        """상대 임포트의 기준이 되는 패키지 경로.

        파이썬의 `__package__` 와 같은 규칙을 따른다. 이걸 틀리면
        `from . import x` 가 한 단계씩 어긋난다.

            routers/auth.py     → module_path "routers.auth", package "routers"
            routers/__init__.py → module_path "routers",      package "routers"
            main.py             → module_path "main",         package ""
        """
        if self.is_package:
            return self.module_path
        head, _, _ = self.module_path.rpartition(".")
        return head


def collect_modules(
    root: Path,
    exclude_patterns: tuple[str, ...] | list[str] | None = None,
    notes: list[AnalysisNote] | None = None,
) -> dict[Path, ModuleInfo]:
    """루트 아래의 파이썬 모듈을 전부 수집한다.

    파싱에 실패한 파일은 노트만 남기고 건너뛴다. 분석 대상 프로젝트에
    문법 오류가 있는 파일 하나가 섞여 있다고 전체 분석이 중단되면 안 된다.

    반환값은 경로순으로 정렬돼 있어, 같은 프로젝트를 두 번 분석하면 항상
    같은 순서가 나온다.
    """
    if not root.is_dir():
        _fail(notes, root, f"분석할 디렉터리가 없습니다: {root}")
        return {}

    modules: dict[Path, ModuleInfo] = {}
    for path in iter_python_files(root, exclude_patterns):
        tree = safe_parse(path, notes)
        if tree is None:
            continue
        modules[path] = ModuleInfo(
            path=path,
            module_path=module_path_of(path, root),
            tree=tree,
            is_package=path.name == "__init__.py",
        )
    return modules


def _fail(notes: list[AnalysisNote] | None, root: Path, message: str) -> None:
    if notes is not None:
        notes.append(
            AnalysisNote(NoteLevel.ERROR, NoteCode.PARSE_FAILED, message, str(root), 0)
        )
