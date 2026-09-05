import asyncio
from backend.document.normalizer import extract_numeric_spans
from backend.navigation.controller import NavigationController
from backend.navigation.state import NavigationStateStore
from backend.playback.manager import PlaybackManager
from backend.tts.rime_client import RimeClient
from backend.utils.logger import log_event


class RequestManager:
    """Cancels and generations TTS requests so late audio can never win."""

    def __init__(self, store: NavigationStateStore, controller: NavigationController,
                 client: RimeClient, playback: PlaybackManager, on_natural_completion=None) -> None:
        self.store = store
        self.controller = controller
        self.client = client
        self.playback = playback
        self._generation = 0
        self._active: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._on_natural_completion = on_natural_completion

    async def interrupt(self) -> None:
        async with self._lock:
            self._generation += 1
            if self._active and not self._active.done():
                self._active.cancel()
                log_event("tts_request_cancelled", request_id=self._generation - 1)
            self._active = None
        await self.playback.flush()

    async def render_current(self, numbers_only: bool = False) -> int | None:
        state = await self.store.read()
        sentence = await self.store.current_sentence()
        if not sentence:
            return None
        text = " ".join(extract_numeric_spans(sentence.raw_text)) if numbers_only else sentence.normalized_text
        async with self._lock:
            self._generation += 1
            request_id = self._generation
            task = asyncio.create_task(self._run(request_id, state.playback_speed, state.current_sentence_id,
                                                 text))
            self._active = task
        await task
        return request_id

    async def _run(self, request_id: int, speed: float, sentence_id: str | None, text: str) -> None:
        log_event("tts_request", request_id=request_id,
              model=getattr(self.client, "default_model", "configured"),
              voice=getattr(self.client, "default_voice", "configured"), speed=speed,
                  sentence_id=sentence_id, text=text, status="started")
        try:
            audio = await self.client.synthesize(
                text,
                getattr(self.client, "default_voice", None),
                getattr(self.client, "default_model", None),
                speed,
            )
            log_event("tts_request", request_id=request_id, sentence_id=sentence_id, status="audio_received")
            async with self._lock:
                current_generation = self._generation
            current_state = await self.store.read()
            if request_id != current_generation or current_state.current_sentence_id != sentence_id:
                log_event("tts_request", request_id=request_id, sentence_id=sentence_id, status="discarded")
                return
            await self.controller.mark_spoken(sentence_id or "")
            await self.controller.set_playing(True)
            await self.playback.play(
                audio,
                request_id,
                on_complete=lambda: self._complete(sentence_id or ""),
            )
            log_event("tts_request", request_id=request_id, sentence_id=sentence_id, status="played")
        except asyncio.CancelledError:
            log_event("tts_request", request_id=request_id, sentence_id=sentence_id, status="cancelled")
            raise
        except Exception:
            log_event("tts_request", request_id=request_id, sentence_id=sentence_id, status="failed")
            return

    async def _complete(self, sentence_id: str) -> None:
        await self.controller.set_playing(False)
        state = await self.controller.advance_after_completion(sentence_id)
        if self._on_natural_completion:
            await self._on_natural_completion(sentence_id, state)

