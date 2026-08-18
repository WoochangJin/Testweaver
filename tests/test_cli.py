from pathlib import Path

from typer.testing import CliRunner

from testweaver import app
from testweaver.loader import load_matrices

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mock_matrix.json"
runner = CliRunner()


def test_select_writes_updated_matrix(tmp_path):
    output_path = tmp_path / "out.json"
    result = runner.invoke(
        app,
        [str(FIXTURE_PATH), "--output", str(output_path)],
        input="1,2\n1\n",
    )

    assert result.exit_code == 0, result.output
    assert output_path.exists()

    matrices = load_matrices(output_path)
    login_selected = {c.id for c in matrices[0].cases if c.selected}
    assert login_selected == {"login-001", "login-003"}  # rows 1,2 in render order


def test_select_reprompts_on_invalid_input(tmp_path):
    output_path = tmp_path / "out.json"
    result = runner.invoke(
        app,
        [str(FIXTURE_PATH), "--output", str(output_path)],
        input="not-a-number\n1\n1\n",
    )

    assert result.exit_code == 0, result.output
    assert "Invalid selection" in result.output