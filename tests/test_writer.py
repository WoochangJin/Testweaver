from pathlib import Path

from testweaver.loader import load_matrices
from testweaver.selection import select_cases
from testweaver.writer import write_matrices

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mock_matrix.json"


def test_write_matrices_round_trips_with_loader(tmp_path):
    matrices = load_matrices(FIXTURE_PATH)
    out_path = tmp_path / "matrix.json"

    write_matrices(matrices, out_path)
    reloaded = load_matrices(out_path)

    assert [m.model_dump() for m in reloaded] == [m.model_dump() for m in matrices]


def test_write_matrices_persists_selection_updates(tmp_path):
    matrices = load_matrices(FIXTURE_PATH)
    login = matrices[0]
    updated_login = select_cases(login, {4, 5})  # login-005, login-004
    matrices[0] = updated_login
    out_path = tmp_path / "matrix.json"

    write_matrices(matrices, out_path)
    reloaded = load_matrices(out_path)

    by_id = {case.id: case.selected for case in reloaded[0].cases}
    assert by_id["login-005"] is True
    assert by_id["login-004"] is True


def test_write_matrices_creates_missing_parent_directories(tmp_path):
    matrices = load_matrices(FIXTURE_PATH)
    out_path = tmp_path / "nested" / "dir" / "matrix.json"

    write_matrices(matrices, out_path)

    assert out_path.exists()