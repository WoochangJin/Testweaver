"""Pipeline orchestration for the TestWeaver CLI.

Keeps the analyze -> case-matrix -> pytest-module chain independent of
CLI argument parsing, so `testweaver/__init__.py` only wires flags to
these functions and each step stays testable without invoking Typer.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from testweaver.analyzer.models import AnalysisResult, Feature
from testweaver.analyzer.pipeline import analyze_project
from testweaver.case_generator.matrix import build_case_matrix
from testweaver.generator import generate_test_module
from testweaver.llm_augment import augment_matrices, get_llm_client
from testweaver.schema import TestCase, TestCaseMatrix


def analyze(project_root: Path) -> AnalysisResult:
    """Statically analyze a FastAPI project and collect its features."""
    return analyze_project(project_root)


_NON_IDENTIFIER_RUN = re.compile(r"[^0-9a-zA-Z_]+")
_BODYLESS_METHODS = frozenset({"GET", "DELETE", "HEAD", "OPTIONS"})


def _normalize_case(case: TestCase, method: str) -> TestCase:
    """Sanitize case_generator output for pytest rendering.

    case_generator ids use "::" as a hierarchy separator, which isn't a
    valid identifier fragment for generator.py's pytest function names.
    It also fills sample_payload regardless of HTTP method, but httpx's
    TestClient.get()/delete()/head()/options() don't accept a json body.
    """
    updates = {"id": _NON_IDENTIFIER_RUN.sub("_", case.id).strip("_")}
    if method.upper() in _BODYLESS_METHODS:
        updates["sample_payload"] = None
    return case.model_copy(update=updates)


def build_matrices(features: list[Feature]) -> list[TestCaseMatrix]:
    """Derive one test case matrix per feature, normalized for pytest rendering."""
    matrices = []
    for feature in features:
        matrix = build_case_matrix(feature)
        cases = [_normalize_case(case, matrix.method) for case in matrix.cases]
        matrices.append(matrix.model_copy(update={"cases": cases}))
    return matrices


def augment_with_llm(matrices: list[TestCaseMatrix], features: list[Feature]) -> list[TestCaseMatrix]:
    """Layer LLM-proposed cases and priority ranking on top of rule-derived matrices.

    No-ops (returns matrices unchanged) when OPENAI_API_KEY isn't set.
    """
    client = get_llm_client()
    return augment_matrices(matrices, features, client)


def generate_pytest_module(matrices: list[TestCaseMatrix]) -> str:
    """Render a pytest module from whichever cases are marked selected."""
    payload = [matrix.model_dump(mode="json") for matrix in matrices]
    return generate_test_module(payload)


def run_tests(path: Path) -> int:
    """Run pytest in-process against the given path and return its exit code."""
    return int(pytest.main([str(path)]))