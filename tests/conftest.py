from pathlib import Path

import pytest

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "sample_app"


@pytest.fixture(scope="session")
def fixture_root() -> Path:
    """분석 대상 샘플 FastAPI 프로젝트의 루트 경로."""
    return FIXTURE_ROOT
