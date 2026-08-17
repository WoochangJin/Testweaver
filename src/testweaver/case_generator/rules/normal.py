from __future__ import annotations

from testweaver.analyzer.models import Feature
from testweaver.case_generator.models import TestCase, TestCaseCategory
from testweaver.case_generator.payload import build_valid_payload


def derive_normal_cases(feature: Feature) -> list[TestCase]:
    return [
        TestCase(
            id=f"{feature.name}::normal::valid_input",
            feature_name=feature.name,
            category=TestCaseCategory.NORMAL,
            description="모든 필드가 유효한 값일 때 정상 응답을 반환한다.",
            expected_status=200,
            sample_payload=build_valid_payload(feature.constraints)
        )
    ]
