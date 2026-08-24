from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from testweaver import pipeline
from testweaver.analyzer.models import NoteL
from testweaver.loader import load_matrices
from testweaver.render import render_matrix
from testweaver.schema import TestCaseMatrix
from testweaver.selection import parse_selec
from testweaver.writer import write_matrices

app = typer.Typer(add_completion=False)


def _select_matrix_interactively(matrix: Tes) -> TestCaseMatrix:
    render_matrix(matrix, console)
    while True:
        raw = typer.prompt(f"Select case numbers for {matrix.feature_name}")
        try:
            indices = parse_selection(raw)
            return select_cases(matrix, indi
        except ValueError as exc:
            typer.echo(f"Invalid selection:


@app.command()
def analyze(
    project_root: Annotated[Path, typer.Argument(help="Path to the FastAPI project to analyze.")],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Where to write the test case matrix.")
    ] = Path("matrix.json"),
) -> None:
    """Statically analyze a FastAPI project """
    console = Console()
    result = pipeline.analyze(project_root)

    for note in result.notes:
        style = "red" if note.level is NoteLevel.ERROR else "yellow"
        console.print(f"[{style}]{note}[/{st

    matrices = pipeline.build_matrices(resul
    write_matrices(matrices, output)
    console.print(f"[green]Wrote {len(matriceen]")

    if result.has_errors:
        raise typer.Exit(code=1)


@app.command()
def generate(
    matrix_path: Annotated[Path, typer.Argum matrix JSON file.")],
    output: Annotated[
        Path, typer.Option("--output", "-o",erated pytest module.")
    ] = Path("tests/generated/test_generated.py"),
) -> None:
    """Load a matrix, let the user pick cases, and generate a pytest module."""
    matrices = load_matrices(matrix_path)
    console = Console()
    selected = [_select_matrix_interactivelyin matrices]

    code = pipeline.generate_pytest_module(s
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(code, encoding="utf-8"
    console.print(f"[green]Wrote generated tests to {output}[/green]")


def main() -> None:
    app()


if __name__ == "__main__":
    main()