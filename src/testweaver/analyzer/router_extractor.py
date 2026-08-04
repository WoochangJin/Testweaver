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


"""
하나의 module에서 Api endpoint를 찾아내는 함수.
파일의 함수를 탐색하며 @router.get 등 router decorator가 붙은 함수를 찾아내 반환함

route 선언에서 알수 있는것만 채움.
여러개의 decorator가 붙은 경우, method마다 Endpoint를 만들어 반환.
리터럴 경로만 읽을 수 있음.
"""
def extract_endpoints(module: ast.Module) -> list[Endpoint]:
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


"""
handler 함수의 인자 중, 요청 body로 쓰일 모델을 찾아 반환.

Depends()를 통한 주입 / int str 같은 단순 타입이 아닌 인자가 요청 body가 됨.
"""
def _find_request_model(handler: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    # 기본값은 인자 목록 뒤쪽부터 붙으므로, 뒤에서부터 짝지어 {인자: 기본값} 맵을 만든다
    #   def f(a, b, c=1, d=2)  →  defaults=[1, 2]는 c, d의 것 
    
    defaults_by_arg = dict(
        zip(handler.args.args[len(handler.args.args) - len(handler.args.defaults):], handler.args.defaults)
    )

    for arg in handler.args.args:
        default = defaults_by_arg.get(arg)

        if isinstance(default, ast.Call) and isinstance(default.func, ast.Name) and default.func.id == "Depends":
            continue

        if isinstance(arg.annotation, ast.Name) and arg.annotation.id not in _BUILTIN_ANNOTATIONS:
            return arg.annotation.id

    return None

