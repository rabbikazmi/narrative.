from typing import Literal

from pydantic import BaseModel, Field


BlockType = Literal["paragraph", "list_item"]
BoundaryType = Literal["section", "page", "paragraph", "list_item", "sentence"]


class Sentence(BaseModel):
    id: str
    raw_text: str
    normalized_text: str
    block_id: str
    block_type: BlockType = "paragraph"
    boundary_before: BoundaryType = "sentence"
    page_number: int = Field(default=1, ge=1)
    position_in_block: int = Field(default=1, ge=1)
    list_marker: str | None = None


class Section(BaseModel):
    id: str
    title: str | None = None
    sentences: list[Sentence] = Field(default_factory=list)


class Document(BaseModel):
    id: str
    name: str
    sections: list[Section] = Field(default_factory=list)
