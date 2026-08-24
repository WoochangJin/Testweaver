from pathlib import Path

from tests.conftest import FIXTURE_ROOT
from testweaver.analyzer.index.file_index import collect_modules
from testweaver.analyzer.models import NoteCode, NoteLevel


def test_collects_every_fixture_module():
    modules = collect_modules(FIXTURE_ROOT)
    module_paths = {m.module_path for m in modules.values()}

    assert "main" in module_paths
    assert "routers.auth" in module_paths
    assert "schemas.base" in module_paths
    assert "services.auth_service" in module_paths


def test_packages_are_flagged_and_anchor_relative_imports():
    """`from . import x` 의 기준점이 되는 package 계산.

    한 단계라도 어긋나면 상대 임포트 해석이 전부 틀어진다.
    """
    modules = {m.module_path: m for m in collect_modules(FIXTURE_ROOT).values()}

    auth = modules["routers.auth"]
    assert auth.is_package is False
    assert auth.package == "routers"

    routers_pkg = modules["routers"]
    assert routers_pkg.is_package is True
    assert routers_pkg.package == "routers"

    assert modules["main"].package == ""


def test_tree_is_parsed_once_and_reusable():
    modules = collect_modules(FIXTURE_ROOT)
    auth = next(m for m in modules.values() if m.module_path == "routers.auth")
    assert auth.tree.body, "AST 가 채워져 있어야 한다"


def test_broken_file_is_skipped_with_a_note(tmp_path: Path):
    (tmp_path / "good.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text("def f(:\n", encoding="utf-8")

    notes: list = []
    modules = collect_modules(tmp_path, notes=notes)

    assert {m.module_path for m in modules.values()} == {"good"}
    assert [n.code for n in notes] == [NoteCode.PARSE_FAILED]


def test_missing_root_reports_error_instead_of_raising(tmp_path: Path):
    notes: list = []
    modules = collect_modules(tmp_path / "does-not-exist", notes=notes)

    assert modules == {}
    assert notes[0].level is NoteLevel.ERROR


def test_exclude_patterns_are_applied(tmp_path: Path):
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    vendor = tmp_path / ".venv" / "lib"
    vendor.mkdir(parents=True)
    (vendor / "vendored.py").write_text("y = 2\n", encoding="utf-8")

    modules = collect_modules(tmp_path)
    assert {m.module_path for m in modules.values()} == {"app"}


def test_result_is_deterministic():
    first = list(collect_modules(FIXTURE_ROOT))
    second = list(collect_modules(FIXTURE_ROOT))
    assert first == second
