from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from backend.metrics import record_first_audio, write_event


router = APIRouter(prefix="/metrics", tags=["metrics"])


class AudioStartedEvent(BaseModel):
    request_id: int
    audio_started_at: float


class ClientMetricEvent(BaseModel):
    metric_type: str
    value_ms: float | None = None
    timestamp: float | None = None
    context: dict[str, object] = Field(default_factory=dict)


@router.post("/audio-started", status_code=204)
async def audio_started(payload: AudioStartedEvent):
    record_first_audio(payload.request_id, payload.audio_started_at)


@router.post("/event", status_code=204)
async def client_metric(request: Request, payload: ClientMetricEvent):
    fields = {"value_ms": payload.value_ms, **payload.context}
    if payload.timestamp is not None:
        fields["timestamp"] = payload.timestamp
    write_event(payload.metric_type, **fields)