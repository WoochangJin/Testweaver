from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from testweaver import pipeline
from testweaver.analyzer.models import NoteLevel
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
def analyze(
    project_root: Annotated[Path, typer.Argument(help="Path to the FastAPI project to analyze.")],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Where to write the test case matrix.")
    ] = Path("matrix.json"),
) -> None:
    """Statically analyze a FastAPI project and write a test case matrix."""
    console = Console()
    result = pipeline.analyze(project_root)

    for note in result.notes:
        style = "red" if note.level is NoteLevel.ERROR else "yellow"
        console.print(f"[{style}]{note}[/{style}]")

    matrices = pipeline.build_matrices(result.features)
    write_matrices(matrices, output)
    console.print(f"[green]Wrote {len(matrices)} matrices to {output}[/green]")

    if result.has_errors:
        raise typer.Exit(code=1)


@app.command()
def generate(
    matrix_path: Annotated[Path, typer.Argument(help="Path to a test case matrix JSON file.")],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Where to write the generated pytest module.")
    ] = Path("tests/generated/test_generated.py"),
) -> None:
    """Load a matrix, let the user pick cases, and generate a pytest module."""
    matrices = load_matrices(matrix_path)
    console = Console()
    selected = [_select_matrix_interactively(matrix, console) for matrix in matrices]

    code = pipeline.generate_pytest_module(selected)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(code, encoding="utf-8")
    console.print(f"[green]Wrote generated tests to {output}[/green]")


@app.command()
def test(
    path: Annotated[
        Path, typer.Argument(help="Path to run pytest against.")
    ] = Path("tests/generated"),
) -> None:
    """Run pytest in-process against generated tests."""
    exit_code = pipeline.run_tests(path)
    raise typer.Exit(code=exit_code)


@app.command()
def run(
    project_root: Annotated[Path, typer.Argument(help="Path to the FastAPI project to analyze.")],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Where to write the generated pytest module.")
    ] = Path("tests/generated/test_generated.py"),
) -> None:
    """Analyze, generate, and run pytest end-to-end without intermediate files."""
    console = Console()
    result = pipeline.analyze(project_root)

    for note in result.notes:
        style = "red" if note.level is NoteLevel.ERROR else "yellow"
        console.print(f"[{style}]{note}[/{style}]")

    if result.has_errors:
        raise typer.Exit(code=1)

    matrices = pipeline.build_matrices(result.features)
    selected = [_select_matrix_interactively(matrix, console) for matrix in matrices]

    code = pipeline.generate_pytest_module(selected)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(code, encoding="utf-8")
    console.print(f"[green]Wrote generated tests to {output}[/green]")

    exit_code = pipeline.run_tests(output)
    raise typer.Exit(code=exit_code)


def main() -> None:
    app()


if __name__ == "__main__":
    main()