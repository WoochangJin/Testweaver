"""Shared pytest fixtures for generated TestWeaver test files.

The `client` fixture is what every generated test function receives
(see src/testweaver/templates/test_case.py.j2 — every test signature is
`def test_x(self, client: TestClient)`). It wires up a FastAPI
TestClient against an in-memory dependency override, so generated
tests can run without any real database or external service.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.fixtures.demo_app.main import app, get_db


@pytest.fixture
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


@pytest.fixture
def client(fresh_db: dict[str, dict[str, Any]]) -> Iterator[TestClient]:
    """FastAPI TestClient with the DB dependency overridden.

    This is the fixture name every generated test expects. Swapping
    `get_db` here is the whole trick: the app under test never touches
    a real database during the generated test run.
    """
    app.dependency_overrides[get_db] = lambda: fresh_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()