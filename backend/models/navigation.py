from pydantic import BaseModel, Field


class NavigationState(BaseModel):
    document_id: str | None = None
    current_section_id: str | None = None
    current_sentence_id: str | None = None
    playback_speed: float = Field(default=1.0, ge=0.5, le=2.0)
    is_playing: bool = False
    last_spoken_id: str | None = None
