from __future__ import annotations

from testweaver.analyzer.models import Feature
from testweaver.case_generator.models import TestCaseMatrix
from testweaver.case_generator.rules import (
    derive_boundary_cases,
    derive_failure_cases,
    derive_normal_cases,
    derive_security_cases,
)


def build_case_matrix(feature: Feature) -> TestCaseMatrix:
    cases = [
        *derive_normal_cases(feature),
        *derive_failure_cases(feature),
        *derive_boundary_cases(feature),
        *derive_security_cases(feature),
    ]
    return TestCaseMatrix(
        feature_name=feature.name,
        endpoint=feature.endpoint.path,
        method=feature.endpoint.method.value,
        cases=cases,
    )