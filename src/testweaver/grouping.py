from __future__ import annotations

from testweaver.schema import CaseCategory, TestCase


def group_cases_by_category(cases: list[TestCase]) -> dict[CaseCategory, list[TestCase]]:
    """Group cases by category, always including every CaseCategory as a key."""
    grouped: dict[CaseCategory, list[TestCase]] = {category: [] for category in CaseCategory}
    for case in cases:
        grouped[case.category].append(case)
    return grouped