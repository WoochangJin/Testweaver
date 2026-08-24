# tests/test_generator.py
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from testweaver.generator import generate_from_file

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GENERATED_DIR = Path(__file__).parent / "_generated"  # tests/ 하위 -> conftest.py 상속됨


@pytest.fixture(autouse=True)
def clean_generated_dir():
    GENERATED_DIR.mkdir(exist_ok=True)
    yield
    shutil.rmtree(GENERATED_DIR, ignore_errors=True)


@pytest.mark.parametrize(
    "matrix_file",
    ["mock_matrix.json", "edge_case_matrix.json"],
)
def test_generated_pytest_file_passes(matrix_file):
    matrix_path = FIXTURES_DIR / matrix_file
    stem = matrix_file.removesuffix(".json")  # 확장자 제거 -> 점 하나만 남게
    output_path = GENERATED_DIR / f"test_generated_{stem}.py"

    # 1) generator.py로 실제 pytest 코드 생성
    generate_from_file(matrix_path, output_path)

    assert output_path.exists()
    generated_code = output_path.read_text(encoding="utf-8")
    assert "def test_" in generated_code

    # 2) tests/ 하위에서 실행 -> conftest.py의 client/fresh_db fixture 자동 상속
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(output_path), "-v"],
        capture_output=True,
        text=True,
        check=False,
        cwd=Path(__file__).parent.parent,
    )

    assert result.returncode == 0, (
        f"생성된 테스트 실패:\n{result.stdout}\n{result.stderr}"
    )