from pathlib import Path

import pytest

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "sample_app"

#: 까다로운 선언 방식만 모아 놓은 두 번째 앱. `fixtures/edge_app/__init__.py` 참고.
EDGE_ROOT = Path(__file__).parent / "fixtures" / "edge_app"


@pytest.fixture(scope="session")
def fixture_root() -> Path:
    """분석 대상 샘플 FastAPI 프로젝트의 루트 경로."""
    return FIXTURE_ROOT


@pytest.fixture(scope="session")
def edge_root() -> Path:
    return EDGE_ROOT
