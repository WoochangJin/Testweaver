from pathlib import Path

import pytest

from testweaver.loader import load_matrices
from testweaver.selection import parse_selection, select_cases, select_cases_globally

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mock_matrix.json"


def test_parse_selection_handles_single_numbers_and_ranges():
    assert parse_selection("1,3,5-7") == {1, 3, 5, 6, 7}


def test_parse_selection_deduplicates_overlap():
    assert parse_selection("1,1,1-2") == {1, 2}


def test_parse_selection_rejects_empty_input():
    with pytest.raises(ValueError):
        parse_selection("   ")


def test_parse_selection_rejects_non_numeric_token():
    with pytest.raises(ValueError):
        parse_selection("1,abc")


def test_parse_selection_rejects_reversed_range():
    with pytest.raises(ValueError):
        parse_selection("5-3")


def test_parse_selection_rejects_zero_or_negative():
    with pytest.raises(ValueError):
        parse_selection("0")


def test_select_cases_marks_only_the_chosen_rows_selected():
    matrices = load_matrices(FIXTURE_PATH)
    login = matrices[0]
    # render order: login-001(1) login-003(2) login-002(3) login-005(4) login-006(5) login-004(6)
    updated = select_cases(login, {4, 6})

    by_id = {case.id: case.selected for case in updated.cases}
    assert by_id["login-005"] is True
    assert by_id["login-004"] is True


def test_select_cases_clears_previously_selected_cases_not_chosen():
    matrices = load_matrices(FIXTURE_PATH)
    login = matrices[0]
    # login-001 and login-002 start selected=True in the fixture
    updated = select_cases(login, {4, 5})

    by_id = {case.id: case.selected for case in updated.cases}
    assert by_id["login-001"] is False
    assert by_id["login-002"] is False


def test_select_cases_does_not_mutate_original_matrix():
    matrices = load_matrices(FIXTURE_PATH)
    login = matrices[0]
    original_flags = [case.selected for case in login.cases]

    select_cases(login, {4})

    assert [case.selected for case in login.cases] == original_flags


def test_select_cases_rejects_out_of_range_index():
    matrices = load_matrices(FIXTURE_PATH)
    login = matrices[0]
    with pytest.raises(ValueError):
        select_cases(login, {99})


def test_select_cases_globally_marks_only_the_chosen_rows_selected():
    matrices = load_matrices(FIXTURE_PATH)
    # global order: login-001(1) login-003(2) login-002(3) login-005(4) login-006(5)
    # login-004(6) profile-001(7) profile-003(8) profile-002(9) profile-004(10)
    updated = select_cases_globally(matrices, {4, 9})

    by_id = {case.id: case.selected for matrix in updated for case in matrix.cases}
    assert by_id["login-005"] is True
    assert by_id["profile-002"] is True
    assert by_id["login-004"] is False
    assert by_id["profile-004"] is False


def test_select_cases_globally_clears_previously_selected_cases_not_chosen():
    matrices = load_matrices(FIXTURE_PATH)
    # login-001 and profile-001 start selected=True in the fixture
    updated = select_cases_globally(matrices, {4, 5})

    by_id = {case.id: case.selected for matrix in updated for case in matrix.cases}
    assert by_id["login-001"] is False
    assert by_id["profile-001"] is False


def test_select_cases_globally_does_not_mutate_original_matrices():
    matrices = load_matrices(FIXTURE_PATH)
    original_flags = [[case.selected for case in matrix.cases] for matrix in matrices]

    select_cases_globally(matrices, {4})

    current_flags = [[case.selected for case in matrix.cases] for matrix in matrices]
    assert current_flags == original_flags


def test_select_cases_globally_rejects_out_of_range_index():
    matrices = load_matrices(FIXTURE_PATH)
    with pytest.raises(ValueError):
        select_cases_globally(matrices, {99})