from pathlib import Path

from testweaver.grouping import group_cases_by_category
from testweaver.loader import load_matrices
from testweaver.schema import CaseCategory, CaseSource
from testweaver.schema import TestCase as SchemaTestCase

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mock_matrix.json"


def _make_case(category: CaseCategory, case_id: str) -> SchemaTestCase:
    return SchemaTestCase(
        id=case_id,
        feature_name="sample",
        category=category,
        description="sample case",
        source=CaseSource.RULE,
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
    assert len(grouped[CaseCategory.FAILURE]) ==  2 # login-002, login-005
