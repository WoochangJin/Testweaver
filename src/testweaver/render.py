from __future__ import annotations

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table

from testweaver.grouping import group_cases_by_category
from testweaver.schema import CaseCategory, FeatureMatrices, TestCase, TestCaseMatrix

def _build_category_table(category: CaseCategory, cases: list[TestCase]) -> Table:
    table = Table(title=category.value.upper(), header_style="bold", expand=True)
    table.add_column("#", width=3)
    table.add_column("ID")
    table.add_column("Description")
    table.add_column("Expected Status")
    table.add_column("Source")
    table.add_column("Selected")
    for index, case in enumerate(cases, start=1):
        table.add_row(
            str(index),
            case.id,
            case.description,
            str(case.expected_status) if case.expected_status is not None else "-",
            case.source.value,
            "yes" if case.selected else "no",
        )
    return table


def render_matrix(matrix: TestCaseMatrix, console: Console) -> None:
    grouped = group_cases_by_category(matrix.cases)
    tables = [
        _build_category_table(category, cases)
        for category, cases in grouped.items()
        if cases
    ]
    body = Group(*tables) if tables else "No test cases"
    console.print(Panel(body, title=f"{matrix.feature_name} - {matrix.method} {matrix.endpoint}"))


def render_matrices(matrices: FeatureMatrices, console: Console | None = None) -> None:
    console = console or Console()
    for matrix in matrices:
        render_matrix(matrix, console)
