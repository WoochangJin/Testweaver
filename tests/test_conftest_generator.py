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

from testweaver.conftest_generator import analyze_state, find_app_entrypoint

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