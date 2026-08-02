"""
Parse python source code into an AST
Provide common AST helpers 
(e.g. finding function definitions, class definitions, etc.)
"""
from __future__ import annotations
import ast
from fnmatch import fnmatch
from pathlib import Path

#read a single python file and return the AST
def parse_file(path: Path) -> ast.Module:
    source = path.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(path))

#iterate over all python files in a directory and its subdirectories
#to yield the path of each file, excluding files that match any of the given patterns
def iter_python_files(root: Path, exclude_patterns: list[str] | None = None):
    exclude_patterns = exclude_patterns or []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if any(_is_excluded(rel, pattern) for pattern in exclude_patterns):
            continue
        yield path

# check if a relative path matches an exclusion pattern
def _is_excluded(rel: str, pattern: str) -> bool:
    if fnmatch(rel, pattern):
        return True

    # check for patterns starting with "**/"
    # (e.g. "**/test_*.py" to exclude all test files in any subdirectory)
    if pattern.startswith("**/"):
        return fnmatch(rel, pattern[3:])
    return False


def get_decorator_call(node: ast.FunctionDef | ast.AsyncFunctionDef, name_suffix: str) -> ast.Call | None:
    #Return the decorator call whose attribute matches `method_name` exactly.
    #(e.g. method_name="get" matches both `@router.get(...)` and `@app.get(...)`)
    
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call):
            func = decorator.func
            if isinstance(func, ast.Attribute) and func.attr == name_suffix:
                return decorator
    return None

def literal_or_none(node: ast.expr | None):
    if node is None:
        return None
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return None