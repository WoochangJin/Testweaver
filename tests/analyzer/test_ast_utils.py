import ast
from pathlib import Path

from tests.conftest import FIXTURE_ROOT
from testweaver.analyzer.ast_utils import (
    UNRESOLVED,
    all_decorator_calls,
    argument_of,
    iter_all_args,
    iter_python_files,
    literal_value,
    module_path_of,
    resolve_status_constant,
    safe_parse,
    split_attribute_call,
    unwrap_annotation,
)
from testweaver.analyzer.models import NoteCode


def _expr(source: str) -> ast.expr:
    return ast.parse(source, mode="eval").body


def _func(source: str) -> ast.FunctionDef:
    return ast.parse(source).body[0]  # type: ignore[return-value]


# ─────────────────── 파일 수집 · 파싱 ───────────────────


def test_iter_python_files_covers_fixture_modules():
    found = {
        p.relative_to(FIXTURE_ROOT).as_posix() for p in iter_python_files(FIXTURE_ROOT)
    }
    assert "main.py" in found
    assert "routers/auth.py" in found
    assert "services/auth_service.py" in found


def test_iter_python_files_applies_exclude_to_relative_path():
    found = {
        p.relative_to(FIXTURE_ROOT).as_posix()
        for p in iter_python_files(FIXTURE_ROOT, ["**/routers/**"])
    }
    assert "main.py" in found
    assert not any(name.startswith("routers/") for name in found)


def test_safe_parse_records_note_instead_of_raising(tmp_path: Path):
    broken = tmp_path / "broken.py"
    broken.write_text("def f(:\n", encoding="utf-8")

    notes: list = []
    assert safe_parse(broken, notes) is None
    assert notes[0].code is NoteCode.PARSE_FAILED


def test_module_path_of():
    assert module_path_of(FIXTURE_ROOT / "main.py", FIXTURE_ROOT) == "main"
    assert (
        module_path_of(FIXTURE_ROOT / "routers" / "auth.py", FIXTURE_ROOT)
        == "routers.auth"
    )
    assert (
        module_path_of(FIXTURE_ROOT / "routers" / "__init__.py", FIXTURE_ROOT)
        == "routers"
    )


# ─────────────────── 리터럴 · 상태코드 ───────────────────


def test_literal_value_distinguishes_none_from_failure():
    assert literal_value(_expr("None")) is None
    assert literal_value(_expr("some.attribute")) is UNRESOLVED
    assert literal_value(_expr("'/login'")) == "/login"


def test_resolve_status_constant_handles_fastapi_idiom():
    assert resolve_status_constant(_expr("404")) == 404
    assert resolve_status_constant(_expr("status.HTTP_404_NOT_FOUND")) == 404
    assert resolve_status_constant(_expr("HTTP_201_CREATED")) == 201
    assert resolve_status_constant(_expr("HTTPStatus.NOT_FOUND")) == 404
    assert resolve_status_constant(_expr("settings.default_status")) is None


# ─────────────────── 호출 인자 ───────────────────


def test_argument_of_accepts_positional_or_keyword():
    call = _expr("router.get('/login', status_code=201)")
    assert literal_value(argument_of(call, 0, "path")) == "/login"
    assert literal_value(argument_of(call, 99, "status_code")) == 201

    call = _expr("router.get(path='/me')")
    assert literal_value(argument_of(call, 0, "path")) == "/me"


def test_split_attribute_call():
    assert split_attribute_call(_expr("router.post('/x')")) == ("router", "post")
    assert split_attribute_call(_expr("app.include_router(r)")) == (
        "app",
        "include_router",
    )


# ─────────────────── 함수 시그니처 ───────────────────


def test_iter_all_args_includes_keyword_only():
    fn = _func("def signup(*, payload: SignupRequest) -> None: ...")
    names = [arg.arg for arg, _ in iter_all_args(fn)]
    assert names == ["payload"]


def test_iter_all_args_pairs_defaults_correctly():
    fn = _func("def f(a, b, c=1, *, d, e=2): ...")
    pairs = {arg.arg: literal_value(default) for arg, default in iter_all_args(fn)}
    assert pairs["a"] is UNRESOLVED  # 기본값 없음
    assert pairs["b"] is UNRESOLVED
    assert pairs["c"] == 1
    assert pairs["d"] is UNRESOLVED
    assert pairs["e"] == 2


def test_real_fixture_keyword_only_handler_is_not_missed():
    """routers/auth.py 의 signup 은 `*, payload` 형태다."""
    tree = safe_parse(FIXTURE_ROOT / "routers" / "auth.py")
    assert tree is not None
    signup = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "signup"
    )
    assert [arg.arg for arg, _ in iter_all_args(signup)] == ["payload"]


def test_all_decorator_calls_keeps_third_party_decorators():
    fn = _func("@limiter.limit('5/min')\n@router.get('/x')\ndef handler(): ...\n")
    attrs = [split_attribute_call(call)[1] for call in all_decorator_calls(fn)]
    assert attrs == ["limit", "get"]


# ─────────────────── 어노테이션 ───────────────────


def test_unwrap_plain_and_dotted():
    assert unwrap_annotation(_expr("LoginRequest")).base_name == "LoginRequest"
    assert unwrap_annotation(_expr("schemas.LoginRequest")).base_name == "LoginRequest"


def test_unwrap_optional_forms():
    for source in ("str | None", "Optional[str]", "Union[str, None]"):
        info = unwrap_annotation(_expr(source))
        assert info.base_name == "str", source
        assert info.is_optional is True, source


def test_unwrap_annotated_keeps_metadata():
    info = unwrap_annotation(_expr("Annotated[str, Query(min_length=3)]"))
    assert info.base_name == "str"
    assert len(info.metadata) == 1
    assert split_attribute_call(info.metadata[0])[1] == "Query"


def test_unwrap_collection_exposes_item_type():
    info = unwrap_annotation(_expr("list[OrderItem]"))
    assert info.is_collection is True
    assert info.item_name == "OrderItem"
    assert info.model_name == "OrderItem"


def test_unwrap_literal_collects_values():
    info = unwrap_annotation(_expr("Literal['active', 'banned']"))
    assert info.literal_values == ["active", "banned"]


def test_unwrap_nested_combination():
    """Annotated[list[Item] | None, Query()] 처럼 겹쳐 쓴 형태."""
    info = unwrap_annotation(_expr("Annotated[list[OrderItem] | None, Query()]"))
    assert info.is_collection is True
    assert info.item_name == "OrderItem"
    assert info.is_optional is True
    assert len(info.metadata) == 1


def test_unwrap_dependency_annotation():
    """실제 픽스처가 쓰는 형태."""
    info = unwrap_annotation(_expr("Annotated[CurrentUser, Depends(get_current_user)]"))
    assert info.base_name == "CurrentUser"
    assert split_attribute_call(info.metadata[0])[1] == "Depends"
