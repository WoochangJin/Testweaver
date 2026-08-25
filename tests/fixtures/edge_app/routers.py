from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from .deps import throttle, verify_token
from .other import Item as Barcode
from .schemas import Item, Node, Search, Tree

# 라우터 단위 인증. 핸들러 어디에도 안 보인다.
secure = APIRouter(prefix="/secure", dependencies=[Depends(verify_token)])

# 중첩 라우터.
inner = APIRouter(prefix="/inner")


@inner.get("/leaf")
def leaf() -> dict:
    return {}


secure.include_router(inner, prefix="/nested")


@secure.get("/items/{sku}", response_model=Item)
def read_item(sku: Annotated[str, Path(min_length=3)]) -> Item:
    return Item(sku=sku)


@secure.post("/barcode")
def make_barcode(payload: Barcode) -> dict:
    """별칭으로 import 한, 이름이 겹치는 모델."""
    return {}


@secure.api_route(
    "/multi", methods=["GET", "POST"], status_code=status.HTTP_202_ACCEPTED
)
def multi() -> dict:
    """데코레이터 하나로 메서드 두 개."""
    return {}


@secure.get("/dual")
@secure.put("/dual")
def dual() -> dict:
    """핸들러 하나에 메서드 데코레이터 두 개."""
    return {}


@secure.post("/search", deprecated=True)
def search(
    body: Search,
    legacy: str | None = Query(default=None, max_length=5),
    mixed: int | None = None,
    limiter: Annotated[str, Depends(throttle)] = "",
) -> dict:
    return {}


@secure.post("/tree")
def make_tree(tree: Tree) -> dict:
    """자기 참조 모델을 품고 있다."""
    return {}


@secure.get("/files/{file_path:path}")
def read_file(file_path: str) -> dict:
    """경로 변환기가 붙은 path 파라미터."""
    return {}


@secure.get("/nodes", response_model=list[Node])
def list_nodes() -> list[Node]:
    return []
