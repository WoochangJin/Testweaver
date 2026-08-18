from __future__ import annotations

from testweaver.analyzer.models import Feature
from testweaver.case_generator.models import TestCase, TestCaseCategory
from testweaver.case_generator.payload import build_valid_payload, build_path_params


def derive_security_cases(feature: Feature) -> list[TestCase]:
    if not feature.endpoint.requires_auth:
        return []
    return [
        TestCase(
            id=f"{feature.name}::security::no_auth",
            feature_name=feature.name,
            category=TestCaseCategory.SECURITY,
            description="인증 정보 없이 보호된 엔드포인트에 접근한다.",
            expected_status=401,
            sample_payload=build_valid_payload(feature.constraints),
            path_params=build_path_params(feature.endpoint.path),
        )
    ]