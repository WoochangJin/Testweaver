"""의존성 주입 지점.

검증 대상:
  · 인증 의존성 판정 — get_current_user 는 401 을, require_admin 은 403 을 낸다.
    이름 휴리스틱만이 아니라 본문의 raise 를 봐야 정확히 구분된다.
  · 전이 의존성 — require_admin 이 다시 get_current_user 에 의존한다.
  · 의존성이 던지는 예외 — 핸들러 본문에는 없으므로 의존성까지 순회해야 잡힌다.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status


class CurrentUser:
    def __init__(self, user_id: int, role: str) -> None:
        self.user_id = user_id
        self.role = role


def get_db() -> object:
    """DB 세션 자리. dependency_overrides 의 주요 대상이다."""
    return object()


def get_current_user(authorization: Annotated[str, Header()] = "") -> CurrentUser:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="NOT_AUTHENTICATED"
        )
    return CurrentUser(user_id=1, role="user")


def require_admin(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN")
    return user
