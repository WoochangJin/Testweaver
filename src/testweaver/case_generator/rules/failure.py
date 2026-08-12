from __future__ import annotations

from testweaver.analyzer.models import Feature
from testweaver.case_generator.models import TestCase, TestCaseCategory



def derive_failure_cases(feature: Feature) -> list[TestCase]:
    return [
        TestCase(
            id=f"{feature.name}::failure::{exc.exception_type}::{index}",
            feature_name=feature.name,
            category=TestCaseCategory.FAILURE,
            description=f"{exc.exception_type} 발생 시 {exc.status_code} 응답을 반환한다.",
            expected_status=exc.status_code,
            expected_error_code=exc.error_code,
        )
        for index, exc in enumerate(feature.endpoint.exceptions)
    ]
