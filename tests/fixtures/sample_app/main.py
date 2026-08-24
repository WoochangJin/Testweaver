"""앱 진입점.

검증 대상:
  · include_router(prefix=...) — 라우터의 실제 경로를 결정하는 곳
  · @app.exception_handler — 커스텀 예외 → 상태코드 매핑
  · 라우터 없이 app 에 직접 붙은 엔드포인트 (health, prefix 없음)
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from .errors import OrderNotFound
from .routers.auth import router as auth_router
from .routers.orders import router as orders_router

app = FastAPI(title="TestWeaver Sample App")

app.include_router(auth_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")


@app.exception_handler(OrderNotFound)
async def handle_order_not_found(request: Request, exc: OrderNotFound) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"code": "ORDER_NOT_FOUND", "order_id": exc.order_id},
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
