"""인증 라우터.

검증 대상:
  · 경로 합성 — APIRouter(prefix="/auth") + include_router(prefix="/api/v1")
    실제 경로는 /api/v1/auth/login 이다. 이 파일만 봐서는 알 수 없다.
  · status_code / response_model — 데코레이터 인자
  · 키워드 전용 인자 — signup 의 `*, payload`
  · Annotated 의존성 — read_me 의 user
  · 호출 그래프 — login 은 raise 가 없지만 authenticate 가 401/423 을 낸다
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from ..deps import CurrentUser, get_current_user
from ..schemas.auth import LoginRequest, SignupRequest, TokenResponse
from ..services.auth_service import authenticate

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    token = authenticate(payload)
    return TokenResponse(access_token=token)


@router.post(
    "/signup", status_code=status.HTTP_201_CREATED, response_model=TokenResponse
)
def signup(*, payload: SignupRequest) -> TokenResponse:
    return TokenResponse(access_token="new-token")


@router.get("/me")
def read_me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> dict:
    return {"user_id": user.user_id}
