from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from testweaver import pipeline
from testweaver.analyzer.models import NoteLevel
from testweaver.loader import load_matrices
from testweaver.render import render_matrices
from testweaver.schema import FeatureMatrices
from testweaver.selection import parse_selection, select_cases_globally
from testweaver.writer import write_matrices

app = typer.Typer(add_completion=False)


def _ensure_utf8_console() -> None:
    """Force UTF-8 I/O on Windows so non-ASCII output doesn't get mangled.

    Windows consoles default to a locale codepage (e.g. cp949), not UTF-8.
    Without this, case ids/descriptions containing non-ASCII text render as
    mojibake (or raise UnicodeEncodeError) unless the user manually sets
    PYTHONUTF8=1 or runs `chcp 65001` first.
    """
    if sys.platform != "win32":
        return
    import ctypes

    ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    ctypes.windll.kernel32.SetConsoleCP(65001)
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def _select_matrices_interactively(
    matrices: FeatureMatrices, console: Console, select_all: bool = False
) -> FeatureMatrices:
    render_matrices(matrices, console)
    total = sum(len(matrix.cases) for matrix in matrices)
    if select_all:
        return select_cases_globally(matrices, parse_selection("all", total))
    while True:
        raw = typer.prompt("Select case numbers")
        try:
            indices = parse_selection(raw, total)
            return select_cases_globally(matrices, indices)
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
    matrices = pipeline.augment_with_llm(matrices, result.features)
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
    select_all: Annotated[
        bool, typer.Option("--all", help="Select every case without prompting.")
    ] = False,
) -> None:
    """Load a matrix, let the user pick cases, and generate a pytest module."""
    matrices = load_matrices(matrix_path)
    console = Console()
    selected = _select_matrices_interactively(matrices, console, select_all=select_all)

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
    select_all: Annotated[
        bool, typer.Option("--all", help="Select every case without prompting.")
    ] = False,
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
    matrices = pipeline.augment_with_llm(matrices, result.features)
    selected = _select_matrices_interactively(matrices, console, select_all=select_all)

    code = pipeline.generate_pytest_module(selected)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(code, encoding="utf-8")
    console.print(f"[green]Wrote generated tests to {output}[/green]")

    conftest_path = pipeline.write_conftest(project_root, output.parent)
    if conftest_path:
        console.print(f"[green]Wrote {conftest_path}[/green]")
    else:
        console.print(
            "[yellow]conftest.py를 자동 생성하지 못했습니다 "
            f"(FastAPI() 진입점을 찾지 못했거나 여러 개 발견됨). "
            f"{output.parent}/conftest.py를 직접 준비해주세요.[/yellow]"
        )

    exit_code = pipeline.run_tests(output)
    raise typer.Exit(code=exit_code)


def main() -> None:
    _ensure_utf8_console()
    app()


if __name__ == "__main__":
    main()