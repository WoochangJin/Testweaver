"""호출 가능한 의존성 클래스. 인스턴스는 다른 모듈(`deps.py`)에서 만든다.

인스턴스와 클래스가 같은 파일에 있다고 가정하면 여기서 깨진다.
"""

from typing import Annotated

from fastapi import Cookie, HTTPException


class RateLimiter:
    def __init__(self, limit: int) -> None:
        self.limit = limit

    def __call__(self, session: Annotated[str, Cookie()] = "") -> str:
        if session == "blocked":
            raise HTTPException(status_code=429, detail="TOO_MANY")
        return session
