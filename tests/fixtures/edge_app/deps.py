from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status


def verify_token(x_api_key: Annotated[str, Header()] = "") -> str:
    """라우터 단위로 걸리는 인증. 핸들러 시그니처에는 나타나지 않는다."""
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="NO_KEY")
    return x_api_key


class RateLimiter:
    """호출 가능한 클래스 인스턴스를 의존성으로 쓰는 형태."""

    def __init__(self, limit: int) -> None:
        self.limit = limit

    def __call__(self, session: Annotated[str, Cookie()] = "") -> str:
        if session == "blocked":
            raise HTTPException(status_code=429, detail="TOO_MANY")
        return session


throttle = RateLimiter(limit=10)


def paging(
    offset: int = 0,
    size: Annotated[int, Depends(lambda: 20)] = 20,
) -> dict:
    return {"offset": offset}
