"""주문 관련 스키마.

검증 대상: 중첩 모델. OrderCreate.items 의 타입은 list[OrderItem] 이므로
어노테이션을 벗겨 내부 모델까지 따라가야 제약을 전부 얻는다.
"""

from pydantic import BaseModel, Field


class OrderItem(BaseModel):
    product_id: int = Field(ge=1)
    quantity: int = Field(default=1, ge=1, le=99)


class OrderCreate(BaseModel):
    items: list[OrderItem]
    memo: str | None = Field(default=None, max_length=200)


class OrderOut(BaseModel):
    id: int
    total: float
