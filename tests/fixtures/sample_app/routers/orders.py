"""주문 라우터.

검증 대상:
  · path 파라미터 — order_id (경로 템플릿과 인자 이름의 대응)
  · query 파라미터 — q / limit / sort. 제약이 Query() 안에 있다
  · 마커 없는 스칼라 인자는 query 로 취급된다는 FastAPI 규칙 (sort)
  · 데코레이터 레벨 의존성 — delete_order 의 dependencies=[...]
  · status 상수 — status.HTTP_404_NOT_FOUND
  · 커스텀 예외 — OrderNotFound 는 전역 핸들러가 404 로 바꾼다
  · 빈 경로("") + prefix 조합
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from ..deps import CurrentUser, get_current_user, get_db, require_admin
from ..errors import OrderNotFound
from ..schemas.order import OrderCreate, OrderOut

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=list[OrderOut])
def list_orders(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    q: Annotated[str | None, Query(min_length=3, max_length=50)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Literal["asc", "desc"] = "asc",
) -> list[OrderOut]:
    return []


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: Annotated[int, Path(ge=1)],
    db: Annotated[object, Depends(get_db)],
) -> OrderOut:
    if order_id == 404:
        raise OrderNotFound(order_id)
    if order_id > 1000:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ORDER_NOT_FOUND"
        )
    return OrderOut(id=order_id, total=0.0)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=OrderOut)
def create_order(
    payload: OrderCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> OrderOut:
    return OrderOut(id=1, total=0.0)


@router.delete(
    "/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_order(order_id: Annotated[int, Path(ge=1)]) -> None:
    return None
