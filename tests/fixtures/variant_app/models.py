from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class Colour(str, Enum):
    RED = "red"
    BLUE = "blue"


class Timestamped(BaseModel):
    created_at: str = Field(min_length=1)


class Named(BaseModel):
    display_name: str = Field(alias="displayName", min_length=2)
    model_config = ConfigDict(populate_by_name=True)


class Product(Timestamped, Named):
    """다중 상속(다이아몬드 아님, 두 부모)."""

    price: Annotated[float, Field(gt=0)]
    colour: Colour = Colour.RED


class Branch(BaseModel):
    """컨테이너 안의 전방 참조."""

    label: str
    children: list["Branch"] = []


class Deep3(BaseModel):
    value: int = Field(ge=0)


class Deep2(BaseModel):
    inner: Deep3


class Deep1(BaseModel):
    middle: Deep2
