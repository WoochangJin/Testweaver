from pathlib import Path

from testweaver.loader import load_matrices
from testweaver.schema import CaseCategory, CaseSource

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mock_matrix.json"


def test_load_matrices_returns_all_feature_matrices():
    matrices = load_matrices(FIXTURE_PATH)
    assert [m.feature_name for m in matrices] == ["login", "get_user_profile"]


def test_load_matrices_parses_case_fields():
    matrices = load_matrices(FIXTURE_PATH)
    login = matrices[0]
    assert login.endpoint == "/api/login"
    assert login.method == "POST"
    first_case = login.cases[0]
    assert first_case.category == CaseCategory.NORMAL
    assert first_case.source == CaseSource.RULE
    assert first_case.selected is True


def test_load_matrices_covers_all_four_categories_per_feature():
    matrices = load_matrices(FIXTURE_PATH)
    for matrix in matrices:
        categories = {case.category for case in matrix.cases}
        assert categories == set(CaseCategory)
