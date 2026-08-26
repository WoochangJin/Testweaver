import re
from pathlib import Path

from rich.console import Console

from testweaver.loader import load_matrices
from testweaver.render import render_matrices, render_matrix

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mock_matrix.json"


def test_render_matrices_prints_feature_and_case_identifiers():
    matrices = load_matrices(FIXTURE_PATH)
    console = Console(record=True, width=120)
    render_matrices(matrices, console=console)
    output = console.export_text()
    assert "login" in output
    assert "get_user_profile" in output
    assert "login-001" in output
    assert "profile-004" in output


def test_render_matrix_handles_missing_category_without_error():
    matrices = load_matrices(FIXTURE_PATH)
    login = matrices[0]
    only_normal = login.model_copy(
        update={"cases": [c for c in login.cases if c.category.value == "normal"]}
    )
    console = Console(record=True, width=120)
    render_matrix(only_normal, console)
    output = console.export_text()
    assert "login-001" in output


def test_render_matrix_shows_category_column():
    matrices = load_matrices(FIXTURE_PATH)
    console = Console(record=True, width=120)
    render_matrix(matrices[0], console)
    output = console.export_text()
    assert "Category" in output
    assert "normal" in output
    assert "boundary" in output


def test_render_matrix_numbers_cases_continuously_across_categories():
    matrices = load_matrices(FIXTURE_PATH)

    def row_number(output: str, case_id: str) -> str:
        match = re.search(rf"(\d+)\D*{case_id}", output)
        assert match, f"row for {case_id} not found"
        return match.group(1)

    login_console = Console(record=True, width=120)
    render_matrix(matrices[0], login_console)
    login_output = login_console.export_text()
    assert row_number(login_output, "login-001") == "1"  # normal
    assert row_number(login_output, "login-003") == "2"  # boundary
    assert row_number(login_output, "login-002") == "3"  # failure
    assert row_number(login_output, "login-006") == "5"  # failure
    assert row_number(login_output, "login-004") == "6"  # security

    profile_console = Console(record=True, width=120)
    render_matrix(matrices[1], profile_console)
    profile_output = profile_console.export_text()
    assert row_number(profile_output, "profile-001") == "1"  # numbering resets per matrix


def test_render_matrices_numbers_continue_across_matrices():
    matrices = load_matrices(FIXTURE_PATH)

    def row_number(output: str, case_id: str) -> str:
        match = re.search(rf"(\d+)\D*{case_id}", output)
        assert match, f"row for {case_id} not found"
        return match.group(1)

    console = Console(record=True, width=120)
    render_matrices(matrices, console=console)
    output = console.export_text()
    assert row_number(output, "login-004") == "6"  # last login row
    assert row_number(output, "profile-001") == "7"  # continues past login's 6
    assert row_number(output, "profile-003") == "8"
    assert row_number(output, "profile-002") == "9"
    assert row_number(output, "profile-004") == "10"


def test_render_matrix_shows_path_params():
    matrices = load_matrices(FIXTURE_PATH)
    profile = matrices[1]
    console = Console(record=True, width=120)
    render_matrix(profile, console)
    output = console.export_text()
    assert "'user_id': 1" in output