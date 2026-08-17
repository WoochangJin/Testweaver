from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

class TestCaseCategory(str, Enum):
    NORMAL = "normal"
    FAILURE = "failure"
    BOUNDARY = "boundary"
    SECURITY = "security"


@dataclass
class TestCase:
    id: str
    feature_name: str
    category: TestCaseCategory
    description: str
    expected_status: int | None = None
    expected_error_code: str | None = None
    source: str = "rule"  #"rule" | "llm"
    selected: bool = False
    sample_payload: dict | None = None


@dataclass
class TestCaseMatrix:
    feature_name: str
    endpoint: str
    method: str
    cases: list[TestCase] = field(default_factory=list)

    def by_category(self, category: TestCaseCategory) -> list[TestCase]:
        return [case for case in self.cases if case.category == category]

    def selected_cases(self) -> list[TestCase]:
        return [case for case in self.cases if case.selected]