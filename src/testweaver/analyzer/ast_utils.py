"""AST 순회에서 반복적으로 필요한 공용 헬퍼.

추출기들이 각자 같은 일을 조금씩 다르게 구현하는 걸 막기 위해 한곳에 모은다.
특히 아래 세 가지는 손으로 구현하면 거의 항상 빠뜨리는 부분이다.

  · 인자 순회 — `fn.args.args` 만 보면 키워드 전용 인자(`def f(*, x)`)를 놓친다.
  · 상태코드 — `ast.literal_eval` 은 `status.HTTP_404_NOT_FOUND` 를 해석하지 못한다.
  · 어노테이션 — `Annotated[str, Query(min_length=3)]` 의 메타데이터에 제약이 들어 있다.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path, PurePosixPath

from testweaver.analyzer.models import AnalysisNote, NoteCode, NoteLevel

DEFAULT_EXCLUDES = (
    "**/.venv/**",
    "**/venv/**",
    "**/site-packages/**",
    "**/node_modules/**",
    "**/__pycache__/**",
    "**/.git/**",
    "**/tests/**",
)

#: 어노테이션에서 원소 타입을 꺼내야 하는 컨테이너들.
_SEQUENCE_TYPES = {
    "list",
    "List",
    "set",
    "Set",
    "frozenset",
    "FrozenSet",
    "tuple",
    "Tuple",
    "Sequence",
    "Iterable",
    "Collection",
}
_MAPPING_TYPES = {"dict", "Dict", "Mapping", "MutableMapping"}


class _Unresolved:
    """리터럴로 해석하지 못한 값. `None` 리터럴과 구분하기 위해 존재한다."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "UNRESOLVED"

    def __bool__(self) -> bool:
        return False


UNRESOLVED = _Unresolved()


# ─────────────────────────── 파일 수집 · 파싱 ───────────────────────────


def iter_python_files(
    root: Path, exclude_patterns: tuple[str, ...] | list[str] | None = None
) -> Iterator[Path]:
    """루트 아래의 .py 파일을 제외 패턴을 적용해 순회한다.

    패턴은 **루트 기준 상대경로**에 대해 매칭한다. 절대경로에 매칭하면
    사용자의 홈 디렉터리 이름 같은 것이 우연히 걸려 들어온다.
    """
    patterns = list(DEFAULT_EXCLUDES if exclude_patterns is None else exclude_patterns)
    for path in sorted(root.rglob("*.py")):
        rel = PurePosixPath(path.relative_to(root).as_posix())
        if any(rel.full_match(pattern) for pattern in patterns):
            continue
        yield path


def safe_parse(
    path: Path, notes: list[AnalysisNote] | None = None
) -> ast.Module | None:
    """파일 하나를 파싱한다. 실패해도 예외를 던지지 않는다.

    분석 대상 프로젝트에는 문법 오류가 있는 파일이나 다른 인코딩의 파일이
    섞여 있을 수 있다. 그 하나 때문에 전체 분석이 중단되면 안 된다.
    """
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        _note(
            notes,
            NoteLevel.WARNING,
            NoteCode.PARSE_FAILED,
            f"파일을 읽지 못했습니다: {exc}",
            path,
        )
        return None
    try:
        return ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        _note(
            notes,
            NoteLevel.WARNING,
            NoteCode.PARSE_FAILED,
            f"문법 오류: {exc.msg}",
            path,
            exc.lineno or 0,
        )
        return None


def module_path_of(path: Path, root: Path) -> str:
    """파일 경로를 루트 기준 점 표기 모듈 경로로 바꾼다.

    root/routers/auth.py     → "routers.auth"
    root/routers/__init__.py → "routers"
    root/main.py             → "main"
    """
    rel = path.relative_to(root)
    parts = list(rel.parts[:-1])
    if rel.stem != "__init__":
        parts.append(rel.stem)
    return ".".join(parts)


def _note(
    notes: list[AnalysisNote] | None,
    level: NoteLevel,
    code: NoteCode,
    message: str,
    path: Path | None = None,
    line: int = 0,
) -> None:
    if notes is not None:
        notes.append(
            AnalysisNote(level, code, message, str(path) if path else "", line)
        )


# ─────────────────────────── 리터럴 · 상태코드 ───────────────────────────


#: 리터럴 하나를 감싸는 수치 생성자. 금액 제약에 흔히 쓰인다.
_NUMERIC_WRAPPERS = {"Decimal", "Fraction"}


def literal_value(node: ast.expr | None):
    """리터럴이면 그 값을, 아니면 `UNRESOLVED` 를 반환한다.

    `None` 을 반환하지 않는 이유는 `x = None` 과 "해석 실패"를 구분해야 하기
    때문이다. 호출부는 `value is UNRESOLVED` 로 확인하라.
    """
    if node is None:
        return UNRESOLVED
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return _wrapped_number(node)


def _wrapped_number(node: ast.expr):
    """`Decimal("0.01")` 처럼 리터럴을 감싼 수치를 풀어 준다.

    금액 필드의 `multiple_of` 나 `ge` 는 부동소수 오차를 피하려고 거의 항상
    이 형태로 적힌다. 그냥 두면 제약이 통째로 사라진다.
    """
    if not isinstance(node, ast.Call) or len(node.args) != 1:
        return UNRESOLVED
    if attribute_or_name(node.func) not in _NUMERIC_WRAPPERS:
        return UNRESOLVED
    inner = literal_value(node.args[0])
    if isinstance(inner, str | int | float):
        try:
            return float(inner)
        except ValueError:
            return UNRESOLVED
    return UNRESOLVED


def resolve_status_constant(node: ast.expr | None) -> int | None:
    """HTTP 상태코드를 정수로 해석한다.

        404                        → 404
        status.HTTP_404_NOT_FOUND  → 404
        HTTPStatus.NOT_FOUND       → 404

    FastAPI 코드는 대부분 `status.HTTP_*` 상수를 쓰는데, 이건 Attribute
    노드라서 `ast.literal_eval` 로는 절대 해석되지 않는다.
    """
    value = literal_value(node)
    if isinstance(value, int):
        return value

    name = attribute_or_name(node)
    if not name:
        return None

    matched = re.fullmatch(r"HTTP_(\d{3})(?:_\w*)?", name)
    if matched:
        return int(matched.group(1))

    try:  # HTTPStatus.NOT_FOUND 같은 멤버 이름
        return int(HTTPStatus[name])
    except KeyError:
        return None


def attribute_or_name(node: ast.expr | None) -> str | None:
    """`x` 는 "x", `a.b.c` 는 "c" 를 반환한다 (가장 끝 이름)."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def split_attribute_call(call: ast.Call) -> tuple[str | None, str | None]:
    """`@router.get(...)` 을 ("router", "get") 으로 나눈다.

    어느 라우터 변수에 붙은 데코레이터인지 알아야 prefix 를 합성할 수 있다.
    """
    func = call.func
    if isinstance(func, ast.Attribute):
        return attribute_or_name(func.value), func.attr
    if isinstance(func, ast.Name):
        return None, func.id
    return None, None


# ─────────────────────────── 호출 인자 ───────────────────────────


def keyword_of(call: ast.Call, name: str) -> ast.expr | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def argument_of(call: ast.Call, position: int, name: str) -> ast.expr | None:
    """위치 인자 또는 키워드 인자 어느 쪽으로 넘어와도 찾아 준다."""
    found = keyword_of(call, name)
    if found is not None:
        return found
    if position < len(call.args):
        return call.args[position]
    return None


def has_keyword(call: ast.Call, name: str) -> bool:
    return any(keyword.arg == name for keyword in call.keywords)


# ─────────────────────────── 함수 시그니처 ───────────────────────────


def iter_all_args(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> Iterator[tuple[ast.arg, ast.expr | None]]:
    """모든 인자를 (인자, 기본값) 쌍으로 순회한다.

    위치 전용 · 일반 · 키워드 전용을 모두 포함한다. `fn.args.args` 만 보면
    `def signup(*, payload: SignupRequest)` 같은 핸들러를 통째로 놓친다.

    기본값이 없으면 두 번째 원소는 파이썬 `None` 이다.
    (`x=None` 인 경우는 `ast.Constant(None)` 이므로 구분된다.)
    """
    positional = [*fn.args.posonlyargs, *fn.args.args]
    defaults = fn.args.defaults
    offset = len(positional) - len(defaults)
    for index, arg in enumerate(positional):
        yield arg, (defaults[index - offset] if index >= offset else None)

    for arg, default in zip(fn.args.kwonlyargs, fn.args.kw_defaults, strict=True):
        yield arg, default


def all_decorator_calls(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.Call]:
    """호출 형태의 데코레이터를 전부 반환한다.

    `@limiter.limit("5/min")` 처럼 서드파티 데코레이터가 함께 붙어 있어도
    라우트 데코레이터를 찾아낼 수 있어야 한다.
    """
    return [d for d in fn.decorator_list if isinstance(d, ast.Call)]


def iter_functions(tree: ast.AST) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield node


# ─────────────────────────── 어노테이션 ───────────────────────────


@dataclass(slots=True)
class AnnotationInfo:
    """타입 어노테이션을 벗겨 낸 결과.

    LoginRequest                      → base_name="LoginRequest"
    schemas.LoginRequest              → base_name="LoginRequest"
    str | None                        → base_name="str", is_optional=True
    Optional[int]                     → base_name="int", is_optional=True
    list[OrderItem]                   → base_name="list", item_name="OrderItem"
    Annotated[str, Query(min_length=3)] → base_name="str", metadata=[Query(...)]
    Literal["active", "banned"]       → literal_values=["active", "banned"]
    """

    base_name: str | None = None
    is_optional: bool = False
    is_collection: bool = False
    item_name: str | None = None
    metadata: list[ast.expr] = field(default_factory=list)
    literal_values: list | None = None
    raw: str = ""

    @property
    def model_name(self) -> str | None:
        """모델일 가능성이 있는 이름. 컨테이너면 원소 타입을 준다."""
        return self.item_name if self.is_collection else self.base_name


def unwrap_annotation(node: ast.expr | None) -> AnnotationInfo:
    """Optional / Annotated / Union / 컨테이너를 벗겨 실제 타입과 메타데이터를 분리한다.

    형태가 겹쳐 쓰이므로(`Annotated[list[Item] | None, Query()]`) 재귀로 처리한다.
    """
    info = AnnotationInfo()
    if node is None:
        return info
    info.raw = ast.unparse(node)
    _unwrap(node, info)
    return info


def _unwrap(node: ast.expr, info: AnnotationInfo) -> None:
    if isinstance(node, ast.Constant) and node.value is None:
        info.is_optional = True
        return

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        # 전방 참조. `child: "Node | None"` 처럼 타입이 문자열로 적힌다.
        # 자기 자신을 품는 모델은 이 형태가 아니면 쓸 수 없다.
        try:
            _unwrap(ast.parse(node.value, mode="eval").body, info)
        except SyntaxError:
            pass
        return

    if isinstance(node, ast.Name):
        if node.id == "None":
            info.is_optional = True
        elif info.base_name is None:
            info.base_name = node.id
        return

    if isinstance(node, ast.Attribute):
        if info.base_name is None:
            info.base_name = node.attr
        return

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        _unwrap(node.left, info)
        _unwrap(node.right, info)
        return

    if isinstance(node, ast.Subscript):
        _unwrap_subscript(node, info)


def _unwrap_subscript(node: ast.Subscript, info: AnnotationInfo) -> None:
    container = attribute_or_name(node.value)
    elements = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
    if not elements:
        return

    if container == "Annotated":
        _unwrap(elements[0], info)
        info.metadata.extend(elements[1:])
        return

    if container == "Optional":
        info.is_optional = True
        _unwrap(elements[0], info)
        return

    if container == "Union":
        for element in elements:
            _unwrap(element, info)
        return

    if container == "Literal":
        values = [literal_value(element) for element in elements]
        info.literal_values = [v for v in values if v is not UNRESOLVED]
        if info.base_name is None:
            info.base_name = "Literal"
        return

    if container in _SEQUENCE_TYPES or container in _MAPPING_TYPES:
        info.is_collection = True
        if info.base_name is None:
            info.base_name = container
        # dict[str, Item] 처럼 매핑이면 값 타입이 관심사다.
        target = elements[-1] if container in _MAPPING_TYPES else elements[0]
        inner = AnnotationInfo()
        _unwrap(target, inner)
        info.item_name = inner.base_name
        if inner.literal_values is not None:
            info.literal_values = inner.literal_values
        return

    # 알 수 없는 제네릭(Page[Item] 등)은 컨테이너 이름만 남긴다.
    if info.base_name is None:
        info.base_name = container
