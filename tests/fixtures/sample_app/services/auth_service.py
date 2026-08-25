"""서비스 계층.

검증 대상: 핸들러 본문 밖에서 발생하는 예외.
routers/auth.py 의 login 핸들러는 raise 를 하나도 갖고 있지 않다.
호출 그래프를 따라 여기까지 와야 401/423 을 발견할 수 있다.

status 상수(status.HTTP_423_LOCKED)도 함께 검증한다 —
ast.literal_eval 로는 해석되지 않는 형태다.
"""

from fastapi import HTTPException, status

from ..schemas.auth import LoginRequest


def authenticate(payload: LoginRequest) -> str:
    if payload.email == "unknown@example.com":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_CREDENTIALS"
        )
    if payload.password == "locked123":
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="ACCOUNT_LOCKED")
    return "issued-token"
