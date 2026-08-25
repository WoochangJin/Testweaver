from typing import Annotated

from pydantic import BaseModel, Field


class Item(BaseModel):
    """다른 모듈에도 같은 이름의 클래스가 있다."""

    sku: str = Field(min_length=3)


class Node(BaseModel):
    """자기 참조. 어노테이션이 문자열로 적힌다."""

    name: str
    child: "Node | None" = None


class Tree(BaseModel):
    root: Node
    depth: Annotated[int, Field(ge=0, le=10)] = 0


class Search(BaseModel):
    keyword: str = Field(min_length=2)
    tags: list[str] | None = None
