from __future__ import annotations

from testweaver.schema import CaseCategory, TestCase


def group_cases_by_category(cases: list[TestCase]) -> dict[CaseCategory, list[TestCase]]:
    """Group cases by category, always including every CaseCategory as a key."""
    grouped: dict[CaseCategory, list[TestCase]] = {category: [] for category in CaseCategory}
    for case in cases:
        grouped[case.category].append(case)
    return grouped


def order_cases_for_selection(cases: list[TestCase]) -> list[TestCase]:
    """Order cases for display/selection.

    When every case carries an LLM-assigned `priority`, cases are sorted by
    that rank ascending (1 = highest priority). Otherwise falls back to the
    category order used since issue #44 (NORMAL -> BOUNDARY -> FAILURE ->
    SECURITY), which is also what a matrix with no LLM ranking (priority is
    None on every case) gets.
    """
    if cases and all(case.priority is not None for case in cases):
        return sorted(cases, key=lambda case: case.priority)
    grouped = group_cases_by_category(cases)
    return [case for group in grouped.values() for case in group]