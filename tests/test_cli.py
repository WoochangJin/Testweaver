from pathlib import Path

from typer.testing import CliRunner

from testweaver import app, pipeline
from testweaver.analyzer.models import AnalysisNote, AnalysisResult, NoteCode, NoteLevel
from testweaver.loader import load_matrices

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mock_matrix.json"
DEMO_APP_ROOT = Path(__file__).parent / "fixtures" / "demo_app"
runner = CliRunner()


def test_analyze_writes_matrix_json(tmp_path):
    output_path = tmp_path / "matrix.json"
    result = runner.invoke(app, ["analyze", str(DEMO_APP_ROOT), "--output", str(output_path)])

    assert result.exit_code == 0, result.output
    assert output_path.exists()
    assert len(load_matrices(output_path)) > 0


def test_analyze_exits_nonzero_on_error_notes(tmp_path, monkeypatch):
    fake_result = AnalysisResult(
        notes=[AnalysisNote(level=NoteLevel.ERROR, code=NoteCode.PARSE_FAILED, message="boom")],
    )
    monkeypatch.setattr(pipeline, "analyze", lambda project_root: fake_result)

    output_path = tmp_path / "matrix.json"
    result = runner.invoke(app, ["analyze", str(DEMO_APP_ROOT), "--output", str(output_path)])

    assert result.exit_code == 1


def test_generate_writes_pytest_module(tmp_path):
    output_path = tmp_path / "test_generated.py"
    result = runner.invoke(
        app,
        ["generate", str(FIXTURE_PATH), "--output", str(output_path)],
        input="1,2\n1\n",
    )

    assert result.exit_code == 0, result.output
    assert output_path.exists()

    code = output_path.read_text(encoding="utf-8")
    assert "class TestLogin" in code
    assert "def test_login_001" in code
    assert "def test_login_003" in code
    assert "def test_login_002" not in code
    assert "class TestGetUserProfile" in code
    assert "def test_profile_001" in code
    assert "def test_profile_002" not in code

    # generate writes straight to the pytest module — no intermediate matrix file
    assert list(tmp_path.iterdir()) == [output_path]


def test_generate_reprompts_on_invalid_input(tmp_path):
    output_path = tmp_path / "test_generated.py"
    result = runner.invoke(
        app,
        ["generate", str(FIXTURE_PATH), "--output", str(output_path)],
        input="not-a-number\n1\n1\n",
    )

    assert result.exit_code == 0, result.output
    assert "Invalid selection" in result.output


def test_test_command_passes_when_pytest_succeeds(tmp_path):
    (tmp_path / "test_cli_pass.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    result = runner.invoke(app, ["test", str(tmp_path)])

    assert result.exit_code == 0, result.output


def test_test_command_propagates_pytest_failure(tmp_path):
    (tmp_path / "test_cli_fail.py").write_text("def test_fail():\n    assert False\n", encoding="utf-8")

    result = runner.invoke(app, ["test", str(tmp_path)])

    assert result.exit_code == 1


def test_test_command_defaults_to_generated_tests_dir(tmp_path, monkeypatch):
    generated_dir = tmp_path / "tests" / "generated"
    generated_dir.mkdir(parents=True)
    (generated_dir / "test_cli_default.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["test"])

    assert result.exit_code == 0, result.output


def test_run_executes_full_pipeline(tmp_path):
    output_path = tmp_path / "test_generated.py"
    result = runner.invoke(
        app,
        ["run", str(DEMO_APP_ROOT), "--output", str(output_path)],
        input="1\n" * 20,  # demo_app 케이스 수만큼 첫 케이스 선택
    )

    assert result.exit_code == 0, result.output
    assert output_path.exists()


def test_run_exits_before_generate_on_analysis_error(tmp_path, monkeypatch):
    fake_result = AnalysisResult(
        notes=[AnalysisNote(level=NoteLevel.ERROR, code=NoteCode.PARSE_FAILED, message="boom")],
    )
    monkeypatch.setattr(pipeline, "analyze", lambda project_root: fake_result)

    output_path = tmp_path / "test_generated.py"
    result = runner.invoke(app, ["run", str(DEMO_APP_ROOT), "--output", str(output_path)])

    assert result.exit_code == 1
    assert not output_path.exists()