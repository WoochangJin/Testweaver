from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, FastAPI, Query, Security, status
from fastapi.security import OAuth2PasswordBearer

from .models import Branch, Colour, Deep1, Product

oauth2 = OAuth2PasswordBearer(tokenUrl="token")


async def current_scopes(token: Annotated[str, Depends(oauth2)]) -> str:
    return token


api = APIRouter()
shared = APIRouter(prefix="/shared")


@shared.get("/ping")
async def shared_ping() -> dict:
    return {}


@api.post("/products", status_code=status.HTTP_201_CREATED)
async def create_product(product: Product) -> dict:
    """별칭이 붙은 필드와 두 부모에서 상속받은 필드를 함께 갖는다."""
    return {}


@api.post("/embed")
async def embed(
    first: Annotated[Product, Body(embed=True)],
    second: Annotated[Branch, Body(embed=True)],
) -> dict:
    """본문 모델이 둘이면 FastAPI 가 이름으로 감싼다."""
    return {}


@api.post("/raw")
async def raw(payload: dict[str, Any]) -> dict:
    """모델이 아닌 본문."""
    return {}


@api.get("/colours/{colour}")
async def by_colour(colour: Colour) -> dict:
    """열거형 path 파라미터."""
    return {}


@api.get("/required-query")
async def required_query(term: Annotated[str, Query(min_length=2)]) -> dict:
    """기본값이 없는 Annotated 쿼리는 필수다."""
    return {}


@api.get("/scoped")
async def scoped(
    user: Annotated[str, Security(current_scopes, scopes=["admin"])],
) -> dict:
    return {}


@api.post("/deep")
async def deep(body: Deep1) -> dict:
    """3단 중첩."""
    return {}


@api.post("/branch")
async def branch(body: Branch) -> dict:
    """컨테이너 안의 자기 참조."""
    return {}


app = FastAPI()
app.include_router(api, prefix="/v1")
# 같은 라우터를 두 곳에 마운트한다.
app.include_router(shared, prefix="/v1")
app.include_router(shared, prefix="/v2")
