"""인증 관련 요청/응답 스키마.

검증 대상:
  · required 판정 — Field에 default가 있는지로 갈린다 (아래 표 참고)
  · 상속 필드 수집 — SignupRequest 는 UserBase.nickname 을 물려받는다
  · allowed_values — Enum(Role), Literal(status)
  · gt/lt — ge/le 로 뭉개면 경계값이 off-by-one 이 된다
  · Annotated 안의 Field 제약
  · @field_validator — 제약을 완전히 표현하지 못한다는 사실을 남겨야 한다
  · 필드가 아닌 것 제외 — model_config

SignupRequest 의 required 기대값:
    nickname (상속)  True    기본값 없음
    email            True    Field(...) = 명시적 필수
    password         True    Field(min_length=8) — default 인자가 없다
    age              False   Field(default=20)
    bio              False   리터럴 기본값
    referrer         False   기본값 None (nullable)
    tags             False   default_factory
    role             True    기본값 없음
    status           False   리터럴 기본값
    score            False   Annotated + 기본값 50
"""

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .base import UserBase


class Role(str, Enum):
    ADMIN = "admin"
    USER = "user"


class LoginRequest(BaseModel):
    email: str = Field(pattern=r"^[^@]+@[^@]+\.[^@]+$")
    password: str = Field(min_length=8, max_length=64)


class SignupRequest(UserBase):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(...)
    password: str = Field(min_length=8)
    age: int = Field(default=20, ge=0, le=120)
    bio: str = "none"
    referrer: str | None = None
    tags: list[str] = Field(default_factory=list)
    role: Role
    status: Literal["active", "banned"] = "active"
    score: Annotated[int, Field(gt=0, lt=100)] = 50

    @field_validator("password")
    @classmethod
    def must_contain_digit(cls, value: str) -> str:
        if not any(char.isdigit() for char in value):
            raise ValueError("password must contain a digit")
        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
