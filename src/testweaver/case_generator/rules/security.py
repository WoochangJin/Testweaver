from __future__ import annotations

from testweaver.analyzer.models import Feature
from testweaver.schema import CaseCategory, CaseSource, TestCase
from testweaver.case_generator.payload import build_path_params, build_valid_payload


def derive_security_cases(feature: Feature) -> list[TestCase]:
    if not feature.endpoint.requires_auth:
        return []
    return [
        TestCase(
            id=f"{feature.name}::security::no_auth",
            feature_name=feature.name,
            category=CaseCategory.SECURITY,   # ← TestCaseCategory.SECURITY 였던 곳
            description="인증 정보 없이 보호된 엔드포인트에 접근한다.",
            expected_status=401,
            sample_payload=build_valid_payload(feature.constraints),
            path_params=build_path_params(feature.endpoint.path),
            source=CaseSource.RULE,           # ← 새로 추가
            )       
    ]