from __future__ import annotations

from testweaver.schema import CaseCategory, TestCase


def group_cases_by_category(cases: list[TestCase]) -> dict[CaseCategory, list[TestCase]]:
    """Group cases by category, always including every CaseCategory as a key."""
    grouped: dict[CaseCategory, list[TestCase]] = {category: [] for category in CaseCategory}
    for case in cases:
        grouped[case.category].append(case)
    return grouped


def order_cases_for_selection(cases: list[TestCase]) -> list[TestCase]:
    """Flatten cases in the same category order used when rendering.

    Keeps selection indices aligned with the row numbers render_matrix prints,
    since both derive from group_cases_by_category's enum ordering.
    """
    grouped = group_cases_by_category(cases)
    return [case for group in grouped.values() for case in group]