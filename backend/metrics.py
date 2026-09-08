import json
import threading
import time
from pathlib import Path
from typing import Any


LOG_PATH = Path(__file__).resolve().parents[1] / "logs" / "metrics.jsonl"
_lock = threading.Lock()
_tts_starts: dict[int, tuple[float, str]] = {}
_tts_content_starts: dict[tuple[str, float], tuple[float, str]] = {}
_last_tts_start: float | None = None


def now_ms() -> float:
    return time.time() * 1000


def write_event(metric_type: str, **fields: Any) -> None:
    event = {
        "timestamp": fields.pop("timestamp", now_ms()),
        "metric_type": metric_type,
        **fields,
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with LOG_PATH.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, separators=(",", ":")) + "\n")


def mark_tts_handoff(request_id: int | None, sentence_id: str | None = None, speed: float | None = None) -> str:
    global _last_tts_start
    started = now_ms()
    tag = "cold" if _last_tts_start is None or started - _last_tts_start > 30_000 else "warm"
    _last_tts_start = started
    if request_id is not None:
        _tts_starts[request_id] = (started, tag)
    if sentence_id is not None and speed is not None:
        _tts_content_starts[(sentence_id, speed)] = (started, tag)
    return tag


def bind_tts_handoff(request_id: int, sentence_id: str, speed: float) -> None:
    started = _tts_content_starts.pop((sentence_id, speed), None)
    if started:
        _tts_starts[request_id] = started


def record_first_audio(request_id: int, audio_started_at: float) -> None:
    started = _tts_starts.pop(request_id, None)
    if not started:
        return
    handed_to_rime, temperature = started
    write_event(
        "time_to_first_audio",
        value_ms=round(audio_started_at - handed_to_rime, 2),
        cold_warm=temperature,
        request_id=request_id,
        handed_to_rime_at=handed_to_rime,
        audio_started_at=audio_started_at,
    )