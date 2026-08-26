"""Tests for conftest_generator against two representative fixture apps.

fixtures/sample_inmemory_crud_app  -- module-level dict + counter mutated in-place, no Depends()
fixtures/sample_depends_only_app   -- Depends(get_db) pattern, no in-module mutation to trace

These fixtures are NOT a real service to run against -- they're fixed,
known-answer inputs that exercise conftest_generator's own AST detection
logic, the same way a parser test feeds in a static code snippet instead
of a live project. Create both fixture directories (see chat) before running.
"""

from pathlib import Path

import pytest

from testweaver.conftest_generator import (
    analyze_state,
    find_app_entrypoint,
    generate_conftest,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_finds_inmemory_crud_app_entrypoint() -> None:
    entrypoint = find_app_entrypoint(FIXTURES / "sample_inmemory_crud_app")
    assert entrypoint.app_var == "app"
    assert entrypoint.module_path == "main"


def test_detects_container_and_counter_in_inmemory_crud_app() -> None:
    entrypoint = find_app_entrypoint(FIXTURES / "sample_inmemory_crud_app")
    result = analyze_state(entrypoint)

    container_names = {c.name for c in result.containers}
    counter_names = {c.name for c in result.counters}

    assert "books_db" in container_names
    assert "next_id" in counter_names
    assert result.counters[0].initial_value_src == "1"
    # sample_inmemory_crud_app doesn't use Depends() at all
    assert result.dependencies == []


def test_falls_back_to_todo_for_unresolvable_depends() -> None:
    entrypoint = find_app_entrypoint(FIXTURES / "sample_depends_only_app")
    result = analyze_state(entrypoint)

    dep_names = {d.name: d.resolved_by_container for d in result.dependencies}
    assert dep_names == {"get_db": False}
    # _USERS is never mutated in sample_depends_only_app, so it must NOT be treated as a container
    assert result.containers == []


def test_raises_on_missing_app() -> None:
    with pytest.raises(ValueError):
        find_app_entrypoint(FIXTURES)


def test_generated_conftest_embeds_absolute_project_root() -> None:
    """The sys.path bootstrap must use an absolute path.

    Otherwise imports break as soon as pytest is invoked from a directory
    other than the target project's own root (e.g. TestWeaver's own repo
    root, which is the normal case for `testweaver run <target>`).
    """
    project_root = (FIXTURES / "sample_inmemory_crud_app").resolve()
    code = generate_conftest(FIXTURES / "sample_inmemory_crud_app")

    assert str(project_root) in code
    assert "sys.path.insert" in code


def test_entrypoint_detection_ignores_test_dirs_relative_to_project_root_only(tmp_path) -> None:
    """A `test`/`tests` segment ABOVE project_root must not exclude files inside it.

    Regression: find_app_entrypoint used to filter on py_file.parts (the full
    absolute path), so a project sitting under e.g. .../Desktop/test/my-project/
    had every one of its files skipped -- "test" matched a parent directory
    that has nothing to do with the project's own test files.
    """
    project_root = tmp_path / "test" / "my-project"
    project_root.mkdir(parents=True)
    (project_root / "main.py").write_text('app = FastAPI(title="x")\n')
    (project_root / "test_main.py").write_text("def test_x(): assert True\n")

    entrypoint = find_app_entrypoint(project_root)
    assert entrypoint.module_path == "main"