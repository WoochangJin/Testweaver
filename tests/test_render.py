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