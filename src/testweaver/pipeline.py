"""Pipeline orchestration for the TestWeaver CLI.

Keeps the analyze -> case-matrix -> pytest-module chain independent of
CLI argument parsing, so `testweaver/__init__.py` only wires flags to
these functions and each step stays testable without invoking Typer.
"""

from __future__ import annotations

from pathlib import Path

from testweaver.analyzer.models import AnalysisResult, Feature
from testweaver.analyzer.pipeline import analyze_project
from testweaver.case_generator.matrix import build_case_matrix
from testweaver.case_generator.models import TestCase as CaseGenTestCase
from testweaver.case_generator.models import TestCaseMatrix as CaseGenMatrix
from testweaver.generator import generate_test_module
from testweaver.schema import CaseCategory, CaseSource, TestCase, TestCaseMatrix


def analyze(project_root: Path) -> AnalysisResult:
    """Statically analyze a FastAPI project and collect its features."""
    return analyze_project(project_root)


def _to_contract_case(case: CaseGenTestCase) -> TestCase:
    """Convert a case_generator dataclass case into the schema.py contract.

    Temporary bridge: case_generator currently builds its own dataclass
    models (testweaver.case_generator.models) instead of the pydantic
    contract in testweaver.schema. Delete this function (and
    _to_contract_matrix) once case_generator builds schema.TestCase directly.
    """
    return TestCase(
        id=case.id,
        feature_name=case.feature_name,
        category=CaseCategory(case.category.value),
        description=case.description,
        expected_status=case.expected_status,
        expected_error_code=case.expected_error_code,
        sample_payload=case.sample_payload,
        path_params=case.path_params,
        source=CaseSource(case.source),
        selected=case.selected,
    )


def _to_contract_matrix(matrix: CaseGenMatrix) -> TestCaseMatrix:
    """Convert a case_generator dataclass matrix into the schema.py contract.

    Temporary bridge, see _to_contract_case.
    """
    return TestCaseMatrix(
        feature_name=matrix.feature_name,
        endpoint=matrix.endpoint,
        method=matrix.method,
        cases=[_to_contract_case(case) for case in matrix.cases],
    )


def build_matrices(features: list[Feature]) -> list[TestCaseMatrix]:
    """Derive one test case matrix per feature, in the schema.py contract shape."""
    return [_to_contract_matrix(build_case_matrix(feature)) for feature in features]


def generate_pytest_module(matrices: list[TestCaseMatrix]) -> str:
    """Render a pytest module from whichever cases are marked selected."""
    payload = [matrix.model_dump(mode="json") for matrix in matrices]
    return generate_test_module(payload)