from testweaver.analyzer.models import Endpoint, Feature, HttpMethod
from testweaver.pipeline import build_matrices, generate_pytest_module, run_tests
from testweaver.schema import CaseCategory, CaseSource


def _mock_feature(**overrides) -> Feature:
    endpoint = Endpoint(
        path=overrides.get("path", "/users"),
        method=HttpMethod.POST,
        handler_name="register",
        requires_auth=overrides.get("requires_auth", False),
    )
    return Feature(
        id=f"{endpoint.method.value} {endpoint.path}",
        name="register",
        endpoint=endpoint,
        constraints=overrides.get("constraints", []),
    )


def test_build_matrices_converts_case_generator_output_to_contract():
    matrices = build_matrices([_mock_feature()])

    assert len(matrices) == 1
    matrix = matrices[0]
    assert matrix.feature_name == "register"
    assert matrix.endpoint == "/users"
    assert matrix.method == "POST"
    assert all(isinstance(case.category, CaseCategory) for case in matrix.cases)
    assert all(isinstance(case.source, CaseSource) for case in matrix.cases)


def test_generate_pytest_module_renders_only_selected_cases():
    matrices = build_matrices([_mock_feature()])
    matrices[0].cases[0].selected = True

    module = generate_pytest_module(matrices)

    assert "import pytest" in module
    assert "class TestRegister" in module


def test_run_tests_returns_pytest_exit_code(tmp_path):
    (tmp_path / "test_pipeline_pass.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )

    assert run_tests(tmp_path) == 0


def test_run_tests_propagates_failure_exit_code(tmp_path):
    (tmp_path / "test_pipeline_fail.py").write_text(
        "def test_fail():\n    assert False\n", encoding="utf-8"
    )

    assert run_tests(tmp_path) == 1