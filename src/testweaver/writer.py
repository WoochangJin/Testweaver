from __future__ import annotations

import json
from pathlib import Path

from testweaver.schema import FeatureMatrices


def write_matrices(matrices: FeatureMatrices, path: str | Path) -> None:
    """Write matrices to path as JSON, in the same shape load_matrices reads.

    Serializes the full matrix structure (all cases, not just selected ones)
    so downstream consumers like generator.generate_from_file can read it
    unchanged.
    """
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = [matrix.model_dump(mode="json") for matrix in matrices]
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")