"""상속 부모 모델.

검증 대상: 자식 모델의 제약을 추출할 때 부모의 필드까지 수집하는가.
부모가 다른 파일에 있으므로 모델 인덱스(크로스 파일 해석)가 없으면 놓친다.
"""

from pydantic import BaseModel, Field


class UserBase(BaseModel):
    nickname: str = Field(min_length=2, max_length=20)
