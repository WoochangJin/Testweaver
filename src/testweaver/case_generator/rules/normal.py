from __future__ import annotations

from testweaver.analyzer.models import Feature
from testweaver.case_generator.payload import build_path_params, build_valid_payload
from testweaver.schema import CaseCategory, CaseSource, TestCase


def derive_normal_cases(feature: Feature) -> list[TestCase]:
    return [
        TestCase(
            id=f"{feature.name}::normal::valid_input",
            feature_name=feature.name,
            category=CaseCategory.NORMAL,
            description="모든 필드가 유효한 값일 때 정상 응답을 반환한다.",
            expected_status=feature.endpoint.success_status_code or 200,
            sample_payload=build_valid_payload(feature.constraints),
            path_params=build_path_params(feature.endpoint.path),
            source=CaseSource.RULE,
        )
    ]