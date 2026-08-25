from __future__ import annotations

from testweaver.analyzer.models import Feature, ParamLocation
from testweaver.case_generator.payload import build_invalid_payload, build_path_params
from testweaver.schema import CaseCategory, CaseSource, TestCase


def derive_boundary_cases(feature: Feature) -> list[TestCase]:
    cases: list[TestCase] = []
    for constraint in feature.constraints_in(ParamLocation.BODY):
        if constraint.required:
            cases.append(_case(feature, constraint.field_name, "missing", f"{constraint.field_name} 필드 누락"))
        if constraint.min_length is not None:
            cases.append(_case(feature, constraint.field_name, "below_min_length", f"{constraint.field_name}이(가) 최소 길이({constraint.min_length}) 미만"))
        if constraint.max_length is not None:
            cases.append(_case(feature, constraint.field_name, "above_max_length", f"{constraint.field_name}이(가) 최대 길이({constraint.max_length}) 초과"))
        if constraint.ge is not None:
            cases.append(_case(feature, constraint.field_name, "below_ge", f"{constraint.field_name}이(가) 최소값({constraint.ge}) 미만"))
        if constraint.le is not None:
            cases.append(_case(feature, constraint.field_name, "above_le", f"{constraint.field_name}이(가) 최대값({constraint.le}) 초과"))
        if constraint.pattern is not None:
            cases.append(_case(feature, constraint.field_name, "pattern_mismatch", f"{constraint.field_name} 형식 오류"))
        if constraint.allowed_values is not None:
            cases.append(_case(feature, constraint.field_name, "invalid_choice", f"{constraint.field_name}이(가) 허용되지 않은 값"))
    return cases


def _case(feature: Feature, field_name: str, variant: str, description: str) -> TestCase:
    return TestCase(
        id=f"{feature.name}::boundary::{field_name}::{variant}",
        feature_name=feature.name,
        category=CaseCategory.BOUNDARY,
        description=description,
        expected_status=422,
        sample_payload=build_invalid_payload(feature.constraints, field_name, variant),
        path_params=build_path_params(feature.endpoint.path),
        source=CaseSource.RULE,
    )