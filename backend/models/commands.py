from enum import StrEnum

from pydantic import BaseModel, Field


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


class CommandRequest(BaseModel):
    text: str = Field(min_length=1)


class VoiceCommandResponse(BaseModel):
    transcript: str
    intent: CommandIntent


class PlaybackConfig(BaseModel):
    voice: str = "mist"
    model: str = "arcana"
