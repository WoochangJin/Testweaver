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
"""Shared pytest fixtures for generated TestWeaver test files.

The `client` fixture is what every generated test function receives
(see src/testweaver/templates/test_case.py.j2 — every test signature is
`def test_x(self, client: TestClient)`). It wires up a FastAPI
TestClient against an in-memory dependency override, so generated
tests can run without any real database or external service.
"""

from collections.abc import Iterator
from typing import Any

from fastapi.testclient import TestClient

from tests.fixtures.demo_app.main import app, get_db


@pytest.fixture(scope="function")
def fresh_db() -> dict[str, dict[str, Any]]:
    """A fresh in-memory user store for every test.

    Function-scoped on purpose: each test gets an isolated DB so one
    test's writes can't leak into another test's assertions. Feature
    dev projects will likely want a similar per-test reset, even if
    the concrete storage differs.
    """
    return {
        "1": {"id": 1, "email": "user@example.com", "password": "correct-pw"},
        "2": {"id": 2, "email": "other@example.com", "password": "whatever"},
    }


@pytest.fixture(scope="function")
def client(fresh_db: dict[str, dict[str, Any]]) -> Iterator[TestClient]:
    """FastAPI TestClient with the DB dependency overridden.

    This is the fixture name every generated test expects. Swapping
    `get_db` here is the whole trick: the app under test never touches
    a real database during the generated test run.

    scope="function" (explicit, matches fresh_db): each test gets its
    own TestClient tied to its own fresh_db. A session-scoped client
    would be faster, but would let dependency_overrides or DB state
    from one test leak into the next — not acceptable for generated
    tests that are meant to run independently and in any order.
    """
    app.dependency_overrides[get_db] = lambda: fresh_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
