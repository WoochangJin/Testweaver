"""LLM-based test case augmentation and priority ranking.

Whether this module does anything is gated on OPENAI_API_KEY: when it's unset,
augment_matrices() returns matrices unchanged, so the pipeline falls back to
the rule-only, category-ordered behavior from issue #44.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

from testweaver.analyzer.models import Feature
from testweaver.schema import CaseCategory, CaseSource, TestCase, TestCaseMatrix

_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = (
    "You are a QA engineer helping design test cases for a FastAPI endpoint. "
    "You are given the endpoint's rule-derived test cases and must (1) propose "
    "additional test cases the rules missed, and (2) rank every case (rule-derived "
    "and newly proposed) by priority, most important first. Only propose cases "
    "that are meaningfully different from the existing ones. Respond with JSON "
    "matching this shape exactly: "
    '{"new_cases": [{"temp_id": str, "category": "normal"|"boundary"|"failure"|"security", '
    '"description": str, "expected_status": int|null, "expected_error_code": str|null, '
    '"sample_payload": object|null, "path_params": object|null}], '
    '"priority_order": [str, ...]}. '
    "priority_order must list every existing case id and every new_cases temp_id exactly once, "
    "most important first."
)


class ChatClient(Protocol):
    """Minimal shape this module needs from an OpenAI client.

    A Protocol (rather than importing `openai.OpenAI` as the type) lets tests
    inject a fake client with no network access and no dependency on the real
    package being installed.
    """

    chat: Any


def get_llm_client() -> ChatClient | None:
    """Build an OpenAI client if OPENAI_API_KEY is set, else None.

    Returning None instead of raising lets callers fall back to the rule-only
    pipeline when no key is configured, rather than failing the whole run.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    from openai import OpenAI

    return OpenAI()


def _feature_context(feature: Feature) -> dict[str, Any]:
    return {
        "endpoint": feature.endpoint.path,
        "method": feature.endpoint.method.value,
        "success_status_code": feature.endpoint.success_status_code,
        "requires_auth": feature.endpoint.requires_auth,
        "requires_permission": feature.endpoint.requires_permission,
        "constraints": [
            {
                "field_name": c.field_name,
                "type_name": c.type_name,
                "required": c.required,
                "location": c.location.value,
                "min_length": c.min_length,
                "max_length": c.max_length,
                "ge": c.ge,
                "le": c.le,
                "gt": c.gt,
                "lt": c.lt,
                "pattern": c.pattern,
                "allowed_values": c.allowed_values,
            }
            for c in feature.constraints
        ],
        "exceptions": [
            {
                "exception_type": e.exception_type,
                "status_code": e.status_code,
                "error_code": e.error_code,
            }
            for e in feature.endpoint.exceptions
        ],
    }


def _existing_case_context(cases: list[TestCase]) -> list[dict[str, Any]]:
    return [
        {
            "id": case.id,
            "category": case.category.value,
            "description": case.description,
            "expected_status": case.expected_status,
        }
        for case in cases
    ]


def _request_augmentation(
    client: ChatClient, feature: Feature, cases: list[TestCase]
) -> dict[str, Any]:
    payload = {
        "feature": _feature_context(feature),
        "existing_cases": _existing_case_context(cases),
    }
    response = client.chat.completions.create(
        model=_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload)},
        ],
    )
    return json.loads(response.choices[0].message.content)


def _build_new_case(feature_name: str, index: int, raw: dict[str, Any]) -> TestCase:
    return TestCase(
        id=f"{feature_name}-llm-{index}",
        feature_name=feature_name,
        category=CaseCategory(raw["category"]),
        description=raw["description"],
        expected_status=raw.get("expected_status"),
        expected_error_code=raw.get("expected_error_code"),
        sample_payload=raw.get("sample_payload"),
        path_params=raw.get("path_params"),
        source=CaseSource.LLM,
    )


def augment_matrix(matrix: TestCaseMatrix, feature: Feature, client: ChatClient) -> TestCaseMatrix:
    """Ask the LLM to propose extra cases and rank the full case set.

    Returns a copy of `matrix`. Rule-derived cases keep their fields except for
    `priority`; any LLM-proposed cases are appended with `source=CaseSource.LLM`.
    Raises ValueError if the model's priority_order doesn't cover every case
    exactly once — a partial or malformed ranking is treated as a contract
    violation rather than something to silently patch over.
    """
    raw = _request_augmentation(client, feature, matrix.cases)
    new_case_specs = raw["new_cases"]

    temp_ids = [spec["temp_id"] for spec in new_case_specs]
    if len(temp_ids) != len(set(temp_ids)):
        raise ValueError(
            f"LLM new_cases for {matrix.feature_name} contains duplicate temp_ids: {temp_ids}"
        )
    existing_ids = {case.id for case in matrix.cases}
    colliding = existing_ids & set(temp_ids)
    if colliding:
        raise ValueError(
            f"LLM new_cases temp_ids collide with existing case ids for {matrix.feature_name}: "
            f"{colliding}"
        )

    new_cases = [
        _build_new_case(matrix.feature_name, i, spec) for i, spec in enumerate(new_case_specs, start=1)
    ]
    by_id: dict[str, TestCase] = {case.id: case for case in matrix.cases}
    by_id.update({spec["temp_id"]: case for spec, case in zip(new_case_specs, new_cases, strict=True)})

    priority_order = raw["priority_order"]
    ranked_ids = set(priority_order)
    if len(priority_order) != len(ranked_ids):
        raise ValueError(
            f"LLM priority_order for {matrix.feature_name} contains duplicate ids: {priority_order}"
        )
    if ranked_ids != set(by_id):
        raise ValueError(
            f"LLM priority_order for {matrix.feature_name} does not match the case set: "
            f"missing={set(by_id) - ranked_ids}, unexpected={ranked_ids - set(by_id)}"
        )

    ranked_cases = [
        by_id[case_id].model_copy(update={"priority": rank})
        for rank, case_id in enumerate(priority_order, start=1)
    ]
    return matrix.model_copy(update={"cases": ranked_cases})


def augment_matrices(
    matrices: list[TestCaseMatrix], features: list[Feature], client: ChatClient | None = None
) -> list[TestCaseMatrix]:
    """Run LLM augmentation over every matrix, or pass them through unchanged.

    `matrices` and `features` must be the same length and in the same order —
    the pairing pipeline.build_matrices() produces (one matrix per feature, in
    order) — since matrix.feature_name alone isn't a reliable join key
    (Feature.id is unique; Feature.name is not).

    `client=None` (the default when OPENAI_API_KEY isn't set) is the fallback
    path: matrices come back exactly as given, preserving the category-ordered
    behavior from issue #44.
    """
    if client is None:
        return matrices
    return [
        augment_matrix(matrix, feature, client)
        for matrix, feature in zip(matrices, features, strict=True)
    ]
