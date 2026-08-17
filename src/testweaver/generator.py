"""pytest test-file generator for TestWeaver.

Takes a test case matrix (see tests/fixtures/mock_matrix.json for the
frozen schema — a list of feature objects, each with a `cases` list)
and renders an executable pytest module using the Jinja2 template in
templates/test_case.py.j2.

Only cases with `selected: true` are rendered. Cases with a null
`expected_status` are rendered as `pytest.skip(...)` rather than
omitted entirely, so the matrix's coverage gaps stay visible in the
generated file instead of silently disappearing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _class_name(feature_name: str) -> str:
    """Convert a snake_case feature name into a PascalCase class name.

    e.g. "get_user_profile" -> "GetUserProfile"
    """
    return "".join(part.capitalize() for part in feature_name.split("_"))


def _prepare_features(matrix: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter to selected cases and attach a render-friendly class_name.

    Features with no selected cases are dropped entirely so we don't
    emit an empty test class.
    """
    prepared = []
    for feature in matrix:
        selected_cases = [c for c in feature["cases"] if c["selected"]]
        if not selected_cases:
            continue
        prepared.append(
            {
                **feature,
                "class_name": _class_name(feature["feature_name"]),
                "cases": selected_cases,
            }
        )
    return prepared


def generate_test_module(matrix: list[dict[str, Any]]) -> str:
    """Render a full pytest module from a matrix JSON structure."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(disabled_extensions=("j2",)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("test_case.py.j2")
    features = _prepare_features(matrix)
    return template.render(features=features)


def generate_from_file(matrix_path: Path, output_path: Path) -> None:
    """Load a matrix JSON file and write the generated pytest module."""
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    code = generate_test_module(matrix)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(code, encoding="utf-8")


if __name__ == "__main__":
    generate_from_file(
        Path("tests/fixtures/mock_matrix.json"),
        Path("tests/generated/test_generated.py"),
    )