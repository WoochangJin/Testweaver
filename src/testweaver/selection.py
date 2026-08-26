from __future__ import annotations

from testweaver.grouping import order_cases_for_selection
from testweaver.schema import FeatureMatrices, TestCaseMatrix


def parse_selection(text: str, total: int) -> set[int]:
    """Parse a selection expression into row numbers.

    Accepts comma-separated numbers/ranges like "1,3,5-7", or the
    case-insensitive keywords "all" (every row from 1 to `total`) and "none"
    (no rows). `total` is needed to expand "all" into concrete indices.
    """
    normalized = text.strip().lower()
    if normalized == "all":
        return set(range(1, total + 1))
    if normalized == "none":
        return set()

    tokens = [token.strip() for token in text.split(",") if token.strip()]
    if not tokens:
        raise ValueError(f"empty selection: {text!r}")

    indices: set[int] = set()
    for token in tokens:
        if "-" in token:
            start_str, _, end_str = token.partition("-")
            start = _parse_positive_int(start_str, token)
            end = _parse_positive_int(end_str, token)
            if start > end:
                raise ValueError(f"invalid range (start > end): {token!r}")
            indices.update(range(start, end + 1))
        else:
            indices.add(_parse_positive_int(token, token))
    return indices


def _parse_positive_int(value: str, token: str) -> int:
    value = value.strip()
    if not value.isdigit():
        raise ValueError(f"invalid selection token: {token!r}")
    parsed = int(value)
    if parsed < 1:
        raise ValueError(f"selection numbers must be >= 1: {token!r}")
    return parsed


def select_cases(matrix: TestCaseMatrix, indices: set[int]) -> TestCaseMatrix:
    """Return a copy of matrix with only the given display indices marked selected.

    Display indices are 1-based and follow the same category ordering used by
    render.render_matrix, so numbers typed against the rendered table map directly
    onto cases here. Replaces the matrix's selection entirely: cases not in
    `indices` come back selected=False regardless of their prior value.
    """
    ordered = order_cases_for_selection(matrix.cases)
    out_of_range = {i for i in indices if i < 1 or i > len(ordered)}
    if out_of_range:
        raise ValueError(f"selection out of range 1-{len(ordered)}: {sorted(out_of_range)}")

    selected_ids = {ordered[i - 1].id for i in indices}
    updated_cases = [
        case.model_copy(update={"selected": case.id in selected_ids})
        for case in matrix.cases
    ]
    return matrix.model_copy(update={"cases": updated_cases})


def select_cases_globally(matrices: FeatureMatrices, indices: set[int]) -> FeatureMatrices:
    """Return copies of matrices with only the given global display indices marked selected.

    Global display indices are 1-based and continue across matrix boundaries, matching
    render_matrices' numbering (each matrix picks up where the previous one left off).
    Replaces each matrix's selection entirely: cases not in `indices` come back
    selected=False regardless of their prior value.
    """
    total = sum(len(matrix.cases) for matrix in matrices)
    out_of_range = {i for i in indices if i < 1 or i > total}
    if out_of_range:
        raise ValueError(f"selection out of range 1-{total}: {sorted(out_of_range)}")

    updated_matrices = []
    offset = 0
    for matrix in matrices:
        local_indices = {i - offset for i in indices if offset < i <= offset + len(matrix.cases)}
        updated_matrices.append(select_cases(matrix, local_indices))
        offset += len(matrix.cases)
    return updated_matrices