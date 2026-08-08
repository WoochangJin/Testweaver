from pathlib import Path

import pytest

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "sample_app"

#: 까다로운 선언 방식만 모아 놓은 두 번째 앱. `fixtures/edge_app/__init__.py` 참고.
EDGE_ROOT = Path(__file__).parent / "fixtures" / "edge_app"

#: 타입과 이름이 까다로운 경우를 모은 세 번째 앱.
VARIANT_ROOT = Path(__file__).parent / "fixtures" / "variant_app"

#: 호출 그래프와 경로 형태가 까다로운 네 번째 앱.
FLOW_ROOT = Path(__file__).parent / "fixtures" / "flow_app"

#: 타입 별칭과 반복 등록을 담은 다섯 번째 앱.
ALIAS_ROOT = Path(__file__).parent / "fixtures" / "alias_app"


@pytest.fixture(scope="session")
def fixture_root() -> Path:
    """분석 대상 샘플 FastAPI 프로젝트의 루트 경로."""
    return FIXTURE_ROOT


@pytest.fixture(scope="session")
def edge_root() -> Path:
    return EDGE_ROOT


@pytest.fixture(scope="session")
def variant_root() -> Path:
    return VARIANT_ROOT
