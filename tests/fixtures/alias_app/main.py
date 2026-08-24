from typing import Annotated, Generic, TypeVar

from fastapi import APIRouter, Depends, FastAPI, Header, Path, Query, status
from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """제네릭 모델."""

    total: int = Field(ge=0)


class Base(BaseModel):
    shared: str = Field(min_length=1)


class Left(Base):
    left_only: int = Field(ge=0)


class Right(Base):
    shared: str = Field(min_length=5)  # 부모를 재정의한다


class Diamond(Left, Right):
    """다이아몬드 상속. shared 는 Right 의 정의가 이겨야 한다(MRO)."""

    own: bool = False


def common(
    trace_id: Annotated[str | None, Header(alias="X-Trace-Id")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
) -> dict:
    return {}


CommonDep = Annotated[dict, Depends(common)]

v1 = APIRouter(prefix="/v1")
v2 = APIRouter(prefix="/v2")


@v1.put(
    "/items/{item_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Page,
    tags=["items", "write"],
)
def replace(
    item_id: Annotated[int, Path(gt=0, le=9999)],
    body: Diamond,
    ctx: CommonDep,
) -> Page:
    """의존성이 타입 별칭 뒤에 숨어 있다."""
    return Page(total=0)


@v2.patch("/items/{item_id}")
def patch_item(item_id: int, ctx: CommonDep) -> dict:
    return {}


app = FastAPI()
for router in (v1, v2):
    app.include_router(router, prefix="/api")
