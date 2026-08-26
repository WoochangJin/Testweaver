"""Auto-generate a project-specific tests/conftest.py for TestWeaver-generated tests.

Two detection passes, in order of confidence:

1. App entrypoint detection
   Walk the target project for a module-level ``x = FastAPI(...)`` call and
   record its dotted import path and variable name.

2. State-reset detection
   Within that entrypoint module, find the mutable state a request handler
   touches so the generated ``client`` fixture can reset it between tests
   without the developer writing that logic by hand:

   - "container" state: a module-level dict/list/set literal whose contents
     are mutated somewhere in the module (subscript assignment, ``del``,
     ``.append``/``.update``/``.clear``/... calls). Reset via ``.clear()``.
   - "counter" state: a module-level int/float literal that is rebound
     inside a function via ``global`` (e.g. an auto-increment id). Reset by
     reassigning the module attribute to its original literal value.
   - "dependency" state: a function used as a FastAPI ``Depends(...)``
     target. If it just returns an already-detected container, no extra
     work is needed (the container reset already covers it). Otherwise we
     can't safely guess a replacement, so we emit a commented TODO instead
     of a silent no-op.

This intentionally does NOT try to guess how to reset a real database
session, an external API client, or anything Depends() resolves to that
isn't traceable back to an in-module container. Those cases fall through
to an explicit TODO in the generated file rather than a wrong guess.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

MUTATING_METHODS = {"append", "pop", "clear", "update", "remove", "extend", "discard", "popitem", "add", "insert"}


@dataclass
class AppEntrypoint:
    module_path: str  # dotted, importable from project root
    app_var: str
    file_path: Path
    project_root: Path  # absolute; embedded in the generated conftest's sys.path bootstrap


@dataclass
class ContainerState:
    name: str
    kind: str  # 'dict' | 'list' | 'set'


@dataclass
class CounterState:
    name: str
    initial_value_src: str  # e.g. "1"


@dataclass
class DependencyState:
    name: str
    resolved_by_container: bool  # True => already covered by a ContainerState reset


@dataclass
class DetectionResult:
    entrypoint: AppEntrypoint
    containers: list[ContainerState] = field(default_factory=list)
    counters: list[CounterState] = field(default_factory=list)
    dependencies: list[DependencyState] = field(default_factory=list)


def find_app_entrypoint(project_root: Path) -> AppEntrypoint:
    """Find the first `x = FastAPI(...)` module-level assignment under project_root."""
    project_root = project_root.resolve()
    candidates: list[AppEntrypoint] = []
    for py_file in sorted(project_root.rglob("*.py")):
        rel_parts = py_file.relative_to(project_root).parts
        if "test" in rel_parts or "tests" in rel_parts or py_file.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                continue
            func = node.value.func
            func_name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if func_name != "FastAPI":
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    rel = py_file.relative_to(project_root).with_suffix("")
                    module_path = ".".join(rel.parts)
                    candidates.append(
                        AppEntrypoint(
                            module_path=module_path,
                            app_var=target.id,
                            file_path=py_file,
                            project_root=project_root,
                        )
                    )
    if not candidates:
        raise ValueError(f"No `x = FastAPI(...)` assignment found under {project_root}")
    if len(candidates) > 1:
        names = ", ".join(c.module_path for c in candidates)
        raise ValueError(f"Multiple FastAPI() instances found ({names}); pass one explicitly")
    return candidates[0]


def _module_level_literal_assigns(tree: ast.Module) -> dict[str, ast.AST]:
    """Name -> value node, for module-level (Ann)Assign with a literal dict/list/set/number value."""
    out: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            out[node.targets[0].id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            out[node.target.id] = node.value
    return out


def _names_mutated_as_container(tree: ast.Module) -> set[str]:
    """Names subscript-assigned, deleted, or method-mutated anywhere in the module."""
    mutated: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
                    mutated.add(t.value.id)
        elif isinstance(node, ast.Delete):
            for t in node.targets:
                if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
                    mutated.add(t.value.id)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in MUTATING_METHODS and isinstance(node.func.value, ast.Name):
                mutated.add(node.func.value.id)
    return mutated


def _names_rebound_via_global(tree: ast.Module) -> set[str]:
    """Names declared `global X` in some function AND reassigned (not just read) there."""
    rebound: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        globals_here = {n for g in ast.walk(node) if isinstance(g, ast.Global) for n in g.names}
        if not globals_here:
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.AugAssign) and isinstance(inner.target, ast.Name) and inner.target.id in globals_here:
                rebound.add(inner.target.id)
            elif isinstance(inner, ast.Assign):
                for t in inner.targets:
                    if isinstance(t, ast.Name) and t.id in globals_here:
                        rebound.add(t.id)
    return rebound


def _depends_target_names(tree: ast.Module) -> set[str]:
    """Function names passed as `Depends(fn)` in any parameter default in the module."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            func_name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if func_name == "Depends" and node.args and isinstance(node.args[0], ast.Name):
                names.add(node.args[0].id)
    return names


def _function_returns_name(tree: ast.Module, fn_name: str) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == fn_name:
            for inner in ast.walk(node):
                if isinstance(inner, ast.Return) and isinstance(inner.value, ast.Name):
                    return inner.value.id
    return None


def analyze_state(entrypoint: AppEntrypoint) -> DetectionResult:
    tree = ast.parse(entrypoint.file_path.read_text(encoding="utf-8"), filename=str(entrypoint.file_path))
    literals = _module_level_literal_assigns(tree)
    mutated_containers = _names_mutated_as_container(tree)
    rebound_counters = _names_rebound_via_global(tree)

    containers: list[ContainerState] = []
    counters: list[CounterState] = []
    for name, value in literals.items():
        if isinstance(value, (ast.Dict, ast.List, ast.Set)) and name in mutated_containers:
            kind = {ast.Dict: "dict", ast.List: "list", ast.Set: "set"}[type(value)]
            containers.append(ContainerState(name=name, kind=kind))
        elif isinstance(value, ast.Constant) and isinstance(value.value, (int, float)) and name in rebound_counters:
            counters.append(CounterState(name=name, initial_value_src=ast.unparse(value)))

    container_names = {c.name for c in containers}
    dependencies: list[DependencyState] = []
    for dep_name in sorted(_depends_target_names(tree)):
        returned = _function_returns_name(tree, dep_name)
        resolved = returned in container_names if returned else False
        dependencies.append(DependencyState(name=dep_name, resolved_by_container=resolved))

    return DetectionResult(entrypoint=entrypoint, containers=containers, counters=counters, dependencies=dependencies)


CONFTEST_TEMPLATE = '''"""Auto-generated by TestWeaver's conftest_generator — do not hand-edit blindly.

Regenerate with: python -m testweaver.conftest_generator <project_root>
If detection missed something (a DB session, an external client, etc.),
fix the TODOs below rather than editing the detection logic per-project.
"""

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# The target project isn't necessarily on sys.path when pytest runs from
# TestWeaver's own working directory, so make it importable explicitly.
_TARGET_PROJECT_ROOT = Path(r"{project_root}")
if str(_TARGET_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_TARGET_PROJECT_ROOT))

from {module_path} import app{extra_imports}
{module_alias_import}

@pytest.fixture(scope="function")
def client() -> Iterator[TestClient]:
    """Fresh TestClient per test; resets in-process state detected in {module_path}."""
{pre_reset}
{overrides}
    with TestClient(app) as test_client:
        yield test_client
{post_reset}{overrides_clear}'''


def render_conftest(result: DetectionResult) -> str:
    module_path = result.entrypoint.module_path
    project_root = result.entrypoint.project_root
    extra_imports = "".join(f", {c.name}" for c in result.containers)

    needs_module_alias = bool(result.counters)
    module_alias_import = f"import {module_path} as _entrypoint_module\n" if needs_module_alias else ""

    pre_reset_lines = [f"    {c.name}.clear()" for c in result.containers]
    for ctr in result.counters:
        pre_reset_lines.append(f"    _entrypoint_module.{ctr.name} = {ctr.initial_value_src}")
    pre_reset = "\n".join(pre_reset_lines) if pre_reset_lines else "    pass"

    override_lines = []
    for dep in result.dependencies:
        if dep.resolved_by_container:
            override_lines.append(f"    # {dep.name}() already resolves to a container reset above; no override needed.")
        else:
            override_lines.append(
                f"    # TODO: `{dep.name}` is used via Depends() but TestWeaver could not trace it to an "
                f"in-module container.\n"
                f"    # app.dependency_overrides[{dep.name}] = lambda: ...  # supply a test double here"
            )
    overrides = "\n".join(override_lines)
    if overrides:
        overrides += "\n"

    post_reset_lines = [f"    {c.name}.clear()" for c in result.containers]
    post_reset = "\n".join(post_reset_lines)
    if post_reset:
        post_reset += "\n"

    has_manual_overrides = any(not d.resolved_by_container for d in result.dependencies)
    overrides_clear = "    app.dependency_overrides.clear()\n" if has_manual_overrides else ""

    return CONFTEST_TEMPLATE.format(
        module_path=module_path,
        project_root=project_root,
        extra_imports=extra_imports,
        module_alias_import=module_alias_import,
        pre_reset=pre_reset,
        overrides=overrides,
        post_reset=post_reset,
        overrides_clear=overrides_clear,
    )


def generate_conftest(project_root: Path) -> str:
    entrypoint = find_app_entrypoint(project_root)
    result = analyze_state(entrypoint)
    return render_conftest(result)


if __name__ == "__main__":
    import sys

    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    print(generate_conftest(root))