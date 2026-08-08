from pydantic import BaseModel, Field


class Item(BaseModel):
    """schemas.Item 과 이름이 같다. import 해석이 제대로 되는지 본다."""

    barcode: str = Field(min_length=8, max_length=13)
    weight: float = Field(gt=0)
