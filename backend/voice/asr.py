from typing import Protocol


class SpeechRecognizer(Protocol):
    async def transcribe(self, audio: bytes) -> str: ...


class FasterWhisperRecognizer:
    """Optional adapter; the model is loaded lazily by the hosting application."""

    def __init__(self, model_size: str = "base") -> None:
        self.model_size = model_size
        self._model = None

    async def transcribe(self, audio: bytes) -> str:
        raise NotImplementedError("Install faster-whisper and provide an audio decoding adapter")
