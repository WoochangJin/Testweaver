from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from testweaver.loader import load_matrices
from testweaver.render import render_matrix
from testweaver.schema import TestCaseMatrix
from testweaver.selection import parse_selection, select_cases
from testweaver.writer import write_matrices

app = typer.Typer(add_completion=False)


def _select_matrix_interactively(matrix: TestCaseMatrix, console: Console) -> TestCaseMatrix:
    render_matrix(matrix, console)
    while True:
        raw = typer.prompt(f"Select case numbers for {matrix.feature_name}")
        try:
            indices = parse_selection(raw)
            return select_cases(matrix, indices)
        except ValueError as exc:
            typer.echo(f"Invalid selection: {exc}", err=True)


@app.command()
def select(
    matrix_path: Annotated[Path, typer.Argument(help="Path to a test case matrix JSON file.")],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Where to write the updated matrix.")
    ] = Path("selected_matrix.json"),
) -> None:
    """Render each feature's test cases and let the user pick which ones to keep."""
    matrices = load_matrices(matrix_path)
    console = Console()
    updated = [_select_matrix_interactively(matrix, console) for matrix in matrices]
    write_matrices(updated, output)
    console.print(f"[green]Wrote {len(updated)} matrices to {output}[/green]")


def main() -> None:
    app()


if __name__ == "__main__":
    main()