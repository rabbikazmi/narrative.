from enum import StrEnum

from pydantic import BaseModel, Field

from backend.models.navigation import NavigationState


class CommandIntent(StrEnum):
    NEXT_SECTION = "NEXT_SECTION"
    PREVIOUS_SECTION = "PREVIOUS_SECTION"
    PREVIOUS_SENTENCE = "PREVIOUS_SENTENCE"
    SKIP = "SKIP"
    REPEAT = "REPEAT"
    SLOW_DOWN = "SLOW_DOWN"
    SPEED_UP = "SPEED_UP"
    READ_NUMBERS = "READ_NUMBERS"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    STOP = "STOP"


class CommandRequest(BaseModel):
    text: str = Field(min_length=1)


class VoiceCommandResponse(BaseModel):
    transcript: str
    intent: CommandIntent
    state: NavigationState
    request_id: int | None = None
    metrics_matched_at: float | None = None
    metrics_expected_section_id: str | None = None
    metrics_expected_sentence_id: str | None = None


class PlaybackConfig(BaseModel):
    voice: str = "mist"
    model: str = "arcana"
