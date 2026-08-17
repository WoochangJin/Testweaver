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


def _resolve_endpoint(endpoint: str, path_params: dict[str, Any] | None) -> str:
    """Fill an endpoint's {placeholders} using the case's path_params.

    Endpoints with no {placeholder} (or cases with no path_params) are
    returned unchanged. Raises KeyError if the matrix is inconsistent
    (endpoint has a placeholder with no matching path_params entry) —
    this is intentional: a silently-wrong URL in generated test code
    is worse than a loud failure at generation time.
    """
    if not path_params:
        return endpoint
    return endpoint.format(**path_params)


def _prepare_features(matrix: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter to selected cases and attach render-friendly fields.

    Features with no selected cases are dropped entirely so we don't
    emit an empty test class. Each case gets a `resolved_endpoint`
    (path_params substituted in) and a `class_name` is attached to the
    feature so the template doesn't need to do any string manipulation.
    """
    prepared = []
    for feature in matrix:
        selected_cases = []
        for case in feature["cases"]:
            if not case["selected"]:
                continue
            resolved_case = {
                **case,
                "resolved_endpoint": _resolve_endpoint(
                    feature["endpoint"], case.get("path_params")
                ),
            }
            selected_cases.append(resolved_case)
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