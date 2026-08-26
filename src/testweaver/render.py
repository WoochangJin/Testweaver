from __future__ import annotations

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table

from testweaver.grouping import group_cases_by_category
from testweaver.schema import CaseCategory, FeatureMatrices, TestCase, TestCaseMatrix


def _build_category_table(category: CaseCategory, cases: list[TestCase], start_index: int) -> Table:
    table = Table(title=category.value.upper(), header_style="bold", expand=True)
    table.add_column("#", width=3)
    table.add_column("ID")
    table.add_column("Description")
    table.add_column("Path Params")
    table.add_column("Expected Status")
    table.add_column("Source")
    table.add_column("Selected")
    for offset, case in enumerate(cases):
        table.add_row(
            str(start_index + offset),
            case.id,
            case.description,
            str(case.path_params) if case.path_params else "-",
            str(case.expected_status) if case.expected_status is not None else "-",
            case.source.value,
            "yes" if case.selected else "no",
        )
    return table


def render_matrix(matrix: TestCaseMatrix, console: Console, start_index: int = 1) -> None:
    grouped = group_cases_by_category(matrix.cases)
    tables = []
    next_index = start_index
    for category, cases in grouped.items():
        if not cases:
            continue
        tables.append(_build_category_table(category, cases, next_index))
        next_index += len(cases)
    body = Group(*tables) if tables else "No test cases"
    console.print(Panel(body, title=f"{matrix.feature_name} - {matrix.method} {matrix.endpoint}"))


def render_matrices(matrices: FeatureMatrices, console: Console | None = None) -> None:
    console = console or Console()
    next_index = 1
    for matrix in matrices:
        render_matrix(matrix, console, next_index)
        next_index += len(matrix.cases)
