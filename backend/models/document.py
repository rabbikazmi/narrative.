from pydantic import BaseModel, Field


class Sentence(BaseModel):
    id: str
    raw_text: str
    normalized_text: str


class Section(BaseModel):
    id: str
    title: str | None = None
    sentences: list[Sentence] = Field(default_factory=list)


class Document(BaseModel):
    id: str
    name: str
    sections: list[Section] = Field(default_factory=list)
