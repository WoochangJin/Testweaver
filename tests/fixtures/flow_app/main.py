from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse

from . import svc
from .sub.routes import router as sub_router


def get_session():
    """yield 의존성."""
    session = {"open": True}
    try:
        yield session
    finally:
        session["open"] = False


api = APIRouter(prefix="/api")
api.include_router(sub_router, prefix="/sub")


@api.get("/chain")
def chain() -> dict:
    """3단 호출 그래프 끝의 409 를 찾아야 한다."""
    svc.level1()
    return {}


@api.get("/domain")
def domain() -> dict:
    """전역 핸들러가 상태코드를 정하는 커스텀 예외."""
    svc.raises_domain()
    return {}


@api.get("/async")
async def async_route(session: Annotated[dict, Depends(get_session)]) -> dict:
    await svc.async_service()
    return {}


@api.get("/framework")
def framework(request: Request, response: Response) -> dict:
    """프레임워크 객체는 입력이 아니다."""
    return {}


app = FastAPI()
app.include_router(api)


@app.exception_handler(svc.DomainError)
async def on_domain(request: Request, exc: svc.DomainError) -> JSONResponse:
    return JSONResponse(status_code=418, content={"code": "DOMAIN"})
