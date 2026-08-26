"""Unit tests for testweaver.scaffold — the conftest.py generator used
to run TestWeaver-generated tests against an arbitrary target project
(instead of this repo's own demo_app fixture)."""

from pathlib import Path

import pytest

from testweaver.scaffold import generate_conftest


def test_writes_import_matching_the_given_app_path(tmp_path):
    output = generate_conftest("main:app", tmp_path / "tests" / "conftest.py")

    content = output.read_text(encoding="utf-8")
    assert "from main import app as app" in content


def test_writes_import_for_nested_module_path(tmp_path):
    output = generate_conftest("src.main:app", tmp_path / "conftest.py")

    content = output.read_text(encoding="utf-8")
    assert "from src.main import app as app" in content


def test_generated_file_defines_client_and_reset_state_fixtures(tmp_path):
    output = generate_conftest("main:app", tmp_path / "conftest.py")

    content = output.read_text(encoding="utf-8")
    assert "def client(" in content
    assert "def reset_state(" in content
    assert "@pytest.fixture" in content


def test_creates_parent_directories(tmp_path):
    output = generate_conftest("pkg.main:app", tmp_path / "a" / "b" / "conftest.py")

    assert output.exists()


@pytest.mark.parametrize("bad_import", ["no_colon_here", "", ":app", "main:"])
def test_rejects_malformed_app_import(tmp_path, bad_import):
    with pytest.raises(ValueError):
        generate_conftest(bad_import, tmp_path / "conftest.py")