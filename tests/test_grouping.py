from pathlib import Path

from testweaver.grouping import group_cases_by_category, order_cases_for_selection
from testweaver.loader import load_matrices
from testweaver.schema import CaseCategory, CaseSource
from testweaver.schema import TestCase as SchemaTestCase

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mock_matrix.json"


def _make_case(
    category: CaseCategory, case_id: str, priority: int | None = None
) -> SchemaTestCase:
    return SchemaTestCase(
        id=case_id,
        feature_name="sample",
        category=category,
        description="sample case",
        source=CaseSource.RULE,
        priority=priority,
    )


def test_group_cases_by_category_includes_every_category_key():
    grouped = group_cases_by_category([])
    assert set(grouped.keys()) == set(CaseCategory)
    assert all(cases == [] for cases in grouped.values())


def test_group_cases_by_category_buckets_cases_correctly():
    cases = [
        _make_case(CaseCategory.NORMAL, "n-1"),
        _make_case(CaseCategory.BOUNDARY, "b-1"),
        _make_case(CaseCategory.NORMAL, "n-2"),
    ]
    grouped = group_cases_by_category(cases)
    assert [c.id for c in grouped[CaseCategory.NORMAL]] == ["n-1", "n-2"]
    assert [c.id for c in grouped[CaseCategory.BOUNDARY]] == ["b-1"]
    assert grouped[CaseCategory.FAILURE] == []
    assert grouped[CaseCategory.SECURITY] == []


def test_group_cases_by_category_matches_fixture_coverage():
    matrices = load_matrices(FIXTURE_PATH)
    login = matrices[0]
    grouped = group_cases_by_category(login.cases)
    assert len(grouped[CaseCategory.NORMAL]) == 1
    assert len(grouped[CaseCategory.FAILURE]) == 3  # login-002, login-005, login-006


def test_order_cases_for_selection_falls_back_to_category_order_without_priority():
    matrices = load_matrices(FIXTURE_PATH)
    login = matrices[0]
    ordered = order_cases_for_selection(login.cases)
    assert [c.id for c in ordered] == [
        "login-001",  # normal
        "login-003",  # boundary
        "login-002",  # failure
        "login-005",  # failure
        "login-006",  # failure
        "login-004",  # security
    ]


def test_order_cases_for_selection_uses_priority_when_every_case_has_one():
    cases = [
        _make_case(CaseCategory.NORMAL, "n-1", priority=3),
        _make_case(CaseCategory.SECURITY, "s-1", priority=1),
        _make_case(CaseCategory.FAILURE, "f-1", priority=2),
    ]
    ordered = order_cases_for_selection(cases)
    assert [c.id for c in ordered] == ["s-1", "f-1", "n-1"]


def test_order_cases_for_selection_falls_back_when_priority_is_partial():
    cases = [
        _make_case(CaseCategory.NORMAL, "n-1", priority=1),
        _make_case(CaseCategory.SECURITY, "s-1", priority=None),
    ]
    ordered = order_cases_for_selection(cases)
    assert [c.id for c in ordered] == ["n-1", "s-1"]  # normal, then security
