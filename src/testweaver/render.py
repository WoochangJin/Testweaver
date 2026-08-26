from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from testweaver.grouping import order_cases_for_selection
from testweaver.schema import FeatureMatrices, TestCase, TestCaseMatrix


def _build_matrix_table(cases: list[TestCase], start_index: int) -> Table:
    table = Table(header_style="bold", expand=True)
    table.add_column("#", width=3)
    table.add_column("ID")
    table.add_column("Category")
    table.add_column("Description")
    table.add_column("Path Params")
    table.add_column("Expected Status")
    table.add_column("Source")
    table.add_column("Selected")
    for offset, case in enumerate(cases):
        table.add_row(
            str(start_index + offset),
            case.id,
            case.category.value,
            case.description,
            str(case.path_params) if case.path_params else "-",
            str(case.expected_status) if case.expected_status is not None else "-",
            case.source.value,
            "yes" if case.selected else "no",
        )
    return table


def render_matrix(matrix: TestCaseMatrix, console: Console, start_index: int = 1) -> None:
    ordered = order_cases_for_selection(matrix.cases)
    body = _build_matrix_table(ordered, start_index) if ordered else "No test cases"
    console.print(Panel(body, title=f"{matrix.feature_name} - {matrix.method} {matrix.endpoint}"))


def render_matrices(matrices: FeatureMatrices, console: Console | None = None) -> None:
    console = console or Console()
    next_index = 1
    for matrix in matrices:
        render_matrix(matrix, console, next_index)
        next_index += len(matrix.cases)
