from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from .limits import RateLimiter


def verify_token(x_api_key: Annotated[str, Header()] = "") -> str:
    """라우터 단위로 걸리는 인증. 핸들러 시그니처에는 나타나지 않는다."""
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="NO_KEY")
    return x_api_key


#: 클래스는 다른 모듈에 있다. 인스턴스에서 클래스를 되짚을 때 import 를 타야 한다.
throttle = RateLimiter(limit=10)


def paging(
    offset: int = 0,
    size: Annotated[int, Depends(lambda: 20)] = 20,
) -> dict:
    return {"offset": offset}
