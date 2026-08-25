from fastapi import FastAPI

from .routers import secure

API_PREFIX = "/api"


def make_ping() -> dict:
    return {"pong": True}


def create_app() -> FastAPI:
    """앱 팩토리. 모듈 최상위에 include_router 가 없다."""
    application = FastAPI()
    application.include_router(secure, prefix=API_PREFIX)
    # 동적 등록. 정적으로는 경로를 알 수 없다.
    application.add_api_route("/ping", make_ping, methods=["GET"])
    return application


app = create_app()
