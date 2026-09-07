import asyncio
import os
import tempfile
from pathlib import Path
from typing import Protocol


MAX_AUDIO_BYTES = 15 * 1024 * 1024
SUPPORTED_AUDIO_SUFFIXES = {".m4a", ".mp3", ".mp4", ".ogg", ".wav", ".webm"}
COMMAND_VOCABULARY = (
    "start reading, play, pause, resume, continue, stop reading, next sentence, "
    "previous sentence, next section, previous section, repeat, slow down, speed up, read numbers"
)


class SpeechRecognizer(Protocol):
    async def transcribe(self, audio: bytes, filename: str | None = None) -> str: ...


class FasterWhisperRecognizer:
    """Transcribe short voice commands with a lazily loaded Faster Whisper model."""

    def __init__(
        self,
        model_size: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
        language: str | None = None,
    ) -> None:
        self.model_size = model_size or os.getenv("WHISPER_MODEL_SIZE", "base.en")
        self.device = device or os.getenv("WHISPER_DEVICE", "cpu")
        self.compute_type = compute_type or os.getenv("WHISPER_COMPUTE_TYPE", "int8")
        configured_language = language if language is not None else os.getenv("WHISPER_LANGUAGE", "en")
        self.language = configured_language or None
        self._model = None
        self._model_lock = asyncio.Lock()

    async def _get_model(self):
        if self._model is not None:
            return self._model
        async with self._model_lock:
            if self._model is None:
                self._model = await asyncio.to_thread(self._load_model)
        return self._model

    def _load_model(self):
        try:
            from faster_whisper import WhisperModel
        except ImportError as error:
            raise RuntimeError(
                'Voice recognition is unavailable. Install the ASR dependencies with pip install -e ".[asr]".'
            ) from error
        return WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )

    def _transcribe_file(self, model, path: str) -> str:
        segments, _ = model.transcribe(
            path,
            language=self.language,
            beam_size=1,
            temperature=0,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 200},
            condition_on_previous_text=False,
            initial_prompt=f"Voice command for a document reader. Valid commands: {COMMAND_VOCABULARY}.",
            hotwords=COMMAND_VOCABULARY,
        )
        return " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()

    async def transcribe(self, audio: bytes, filename: str | None = None) -> str:
        if not audio:
            raise ValueError("The recording was empty. Please hold the microphone button and speak again.")
        if len(audio) > MAX_AUDIO_BYTES:
            raise ValueError("The recording is too large. Keep voice commands under 10 seconds.")

        suffix = Path(filename or "command.webm").suffix.lower()
        if suffix not in SUPPORTED_AUDIO_SUFFIXES:
            suffix = ".webm"

        model = await self._get_model()
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as recording:
                recording.write(audio)
                temporary_path = Path(recording.name)
            transcript = await asyncio.to_thread(self._transcribe_file, model, str(temporary_path))
        except ValueError:
            raise
        except Exception as error:
            raise RuntimeError("The voice command could not be decoded or transcribed.") from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        if not transcript:
            raise ValueError("No speech was recognized. Please try the command again.")
        return transcript
