"""소스에서 API endpoint(경로 + method + handler)를 찾아내는 모듈.

대상 파일에 어떤 Api가 있는지 찾아냄. 
"""

from __future__ import annotations
import ast
from testweaver.analyzer.ast_utils import get_decorator_call, literal_or_none
from testweaver.analyzer.models import Endpoint, HttpMethod

# 탐색할 router decorator. (e.g. @app.get("/path")의 get)
_HTTP_METHODS = [m.value.lower() for m in HttpMethod]

# 요청 body가 아니라 path/query parameter로 쓰이는 단순 타입들.
# 이 타입이 붙은 인자는 body 후보에서 제외
_BUILTIN_ANNOTATIONS = {"int", "str", "float", "bool", "UUID"}

# Annotated 안에 붙어 "이건 body가 아니다"를 뜻하는 marker들
_NON_BODY_MARKERS = {"Depends", "Query", "Path", "Header", "Cookie",
                     "Form", "File", "Security"}

# 대괄호 표기 중 안쪽에 실제 model이 들어 있는 것들
_UNWRAP_CONTAINERS = {"Annotated", "Optional", "Union"}


def extract_endpoints(module: ast.Module) -> list[Endpoint]:
    """
    하나의 module에서 Api endpoint를 찾아내는 함수.
    파일의 함수를 탐색하며 @router.get 등 router decorator가 붙은 함수를 찾아내 반환함

    route 선언에서 알수 있는것만 채움.
    여러개의 decorator가 붙은 경우, method마다 Endpoint를 만들어 반환.
    리터럴 경로만 읽을 수 있음.
    """
    endpoints: list[Endpoint] = []
    for node in ast.walk(module):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for method_name in _HTTP_METHODS:
            call = get_decorator_call(node, method_name)
            if call is None:
                continue
            path = literal_or_none(call.args[0]) if call.args else None
            endpoints.append(
                Endpoint(
                    path=path or "",
                    method=HttpMethod(method_name.upper()),
                    handler_name=node.name,
                    request_model=_find_request_model(node),
                )
            )
    return endpoints


def _find_request_model(handler: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """
    handler 함수의 인자 중, 요청 body로 쓰일 모델을 찾아 반환.

    Depends()를 통한 주입 / int str 같은 단순 타입이 아닌 인자가 요청 body가 됨.
    """
    # 기본값은 인자 목록 뒤쪽부터 붙으므로, 뒤에서부터 짝지어 {인자: 기본값} 맵을 만든다
    #   def f(a, b, c=1, d=2)  →  defaults=[1, 2]는 c, d의 것 
    defaults_by_arg = dict(
        zip(handler.args.args[len(handler.args.args) - len(handler.args.defaults):], handler.args.defaults)
    )

    for arg in handler.args.args:
        default = defaults_by_arg.get(arg)

        if isinstance(default, ast.Call) and isinstance(default.func, ast.Name) and default.func.id == "Depends":
            continue

        if _has_non_body_marker(arg.annotation):
            continue

        name = _annotation_name(arg.annotation)
        if name is not None and name not in _BUILTIN_ANNOTATIONS:
            return name

    return None


def _annotation_name(node: ast.expr | None) -> str | None:
    """애노테이션에서 model 이름을 꺼낸다.

    타입을 적는 방식이 다양함 & AST에서는 형태마다 노드 종류가 다름
    따라서 각각을 나눠 처리.

        LoginRequest                    → "LoginRequest"
        schemas.LoginRequest            → "LoginRequest"   (뒤쪽 이름만)
        Annotated[LoginRequest, Body()] → "LoginRequest"   (첫 번째 것만)
        LoginRequest | None             → "LoginRequest"   (None이 아닌 쪽)
        Optional[LoginRequest]          → "LoginRequest"

    형태가 겹쳐 쓰일 수 있어(Annotated[schemas.X, ...]) 재귀로 탐색.
    알아볼 수 없는 형태면 None을 반환.
    """
    if isinstance(node, ast.Name):                  # LoginRequest
        return node.id

    if isinstance(node, ast.Attribute):             # schemas.LoginRequest
        return node.attr

    if isinstance(node, ast.Subscript):             # 대괄호가 붙은 형태
        if _annotation_name(node.value) not in _UNWRAP_CONTAINERS:
            return None                             # list[Item] 등은 body가 아님
        elts = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        for elt in elts:
            name = _annotation_name(elt)
            if name is not None:
                return name
        return None

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):   # X | None
        return _annotation_name(node.left) or _annotation_name(node.right)

    return None


def _has_non_body_marker(node: ast.expr | None) -> bool:
    """Annotated[...] 안에 Depends()/Query() 같은 marker가 있는지 확인.

    FastAPI 신식 표기는 기본값 대신 Annotated 안에 주입을 작성.

        Annotated[User, Depends(get_user)]   → 주입, body 아님
        Annotated[str, Query()]              → query parameter, body 아님
        Annotated[ItemIn, Body()]            → body 맞음
    """
    if not isinstance(node, ast.Subscript):
        return False
    elts = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
    return any(
        isinstance(elt, ast.Call) and _annotation_name(elt.func) in _NON_BODY_MARKERS
        for elt in elts
    )