from pydantic import BaseModel, Field


class Item(BaseModel):
    """schemas.Item 과 이름이 같다. import 해석이 제대로 되는지 본다."""

    barcode: str = Field(min_length=8, max_length=13)
    weight: float = Field(gt=0)


class RateLimiter:
    """limits.RateLimiter 와 이름이 같다.

    이름만으로 클래스를 찾으면 여기서 후보가 둘이 되어 특정에 실패한다.
    인스턴스를 선언한 모듈의 import 를 타야 정확히 골라낼 수 있다.
    """

    def __call__(self) -> None:
        return None
