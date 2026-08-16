from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

class CaseCategory(str, Enum):
    """Categories used to classify generated test cases."""

    NORMAL = "normal"
    BOUNDARY = "boundary"
    FAILURE = "failure"
    SECURITY = "security"

class CaseSource(str, Enum):
    RULE = "rule"
    LLM = "llm"

class TestCase(BaseModel):
    """Represents a single test case generated for a feature."""

    id: str
    feature_name: str
    category: CaseCategory
    description: str
    expected_status: int | None = None
    expected_error_code: str | None = None
    sample_payload: dict | None = None
    source: CaseSource
    selected: bool = False

class TestCaseMatrix(BaseModel):

    feature_name: str
    endpoint: str
    method: str
    cases: list[TestCase]

FeatureMatrices = list[TestCaseMatrix]