from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from testweaver.schema import FeatureMatrices, TestCaseMatrix

_matrices_adapter = TypeAdapter(list[TestCaseMatrix])


def load_matrices(path: str | Path) -> FeatureMatrices:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return _matrices_adapter.validate_python(data)