import asyncio
from backend.document.normalizer import extract_numeric_spans, normalize_text
from backend.models.document import Sentence
from backend.navigation.controller import NavigationController
from backend.navigation.state import NavigationStateStore
from backend.playback.manager import PlaybackManager
from backend.tts.rime_client import RimeClient
from backend.utils.logger import log_event
from backend.metrics import bind_tts_handoff, mark_tts_handoff


class RequestManager:
    """Cancels and generations TTS requests so late audio can never win."""

    def __init__(self, store: NavigationStateStore, controller: NavigationController,
                 client: RimeClient, playback: PlaybackManager) -> None:
        self.store = store
        self.controller = controller
        self.client = client
        self.playback = playback
        self._generation = 0
        self._active: asyncio.Task[None] | None = None
        self._prefetch_task: asyncio.Task[None] | None = None
        self._prefetch_target: tuple[str, float] | None = None
        self._prefetched: tuple[str, float, bytes] | None = None
        self._lock = asyncio.Lock()

    async def interrupt(self) -> None:
        async with self._lock:
            self._generation += 1
            if self._active and not self._active.done():
                self._active.cancel()
                log_event("tts_request_cancelled", request_id=self._generation - 1)
            if self._prefetch_task and not self._prefetch_task.done():
                self._prefetch_task.cancel()
            self._active = None
            self._prefetch_task = None
            self._prefetch_target = None
            self._prefetched = None
        await self.playback.flush()

    async def render_current(self, numbers_only: bool = False,
                             announce_section: bool | None = None) -> int | None:
        state = await self.store.read()
        sentence = await self.store.current_sentence()
        if not sentence:
            return None
        text = " ".join(extract_numeric_spans(sentence.raw_text)) if numbers_only else sentence.normalized_text
        should_announce = (
            sentence.boundary_before == "section"
            if announce_section is None
            else announce_section
        )
        if should_announce and not numbers_only:
            text = await self._speech_text(sentence, include_section=True)

        prefetch_task = None
        if not numbers_only:
            async with self._lock:
                if self._prefetch_target == (sentence.id, state.playback_speed):
                    prefetch_task = self._prefetch_task
        if prefetch_task:
            try:
                await prefetch_task
            except asyncio.CancelledError:
                pass

        async with self._lock:
            prefetched_audio = None
            if not numbers_only and self._prefetched:
                prefetched_id, prefetched_speed, audio = self._prefetched
                if (prefetched_id, prefetched_speed) == (sentence.id, state.playback_speed):
                    prefetched_audio = audio
            self._prefetch_task = None
            self._prefetch_target = None
            self._prefetched = None
            self._generation += 1
            request_id = self._generation
            if prefetched_audio is not None:
                bind_tts_handoff(request_id, sentence.id, state.playback_speed)
                task = asyncio.create_task(self._deliver(
                    request_id, state.current_sentence_id, prefetched_audio, "prefetched",
                ))
            else:
                task = asyncio.create_task(self._run(
                    request_id, state.playback_speed, state.current_sentence_id, text,
                ))
            self._active = task
        await task
        if self.playback.request_id() == request_id:
            await self._schedule_prefetch(request_id, sentence.id, state.playback_speed)
        return request_id

    async def _run(self, request_id: int, speed: float, sentence_id: str | None, text: str) -> None:
        log_event("tts_request", request_id=request_id,
              model=getattr(self.client, "default_model", "configured"),
              voice=getattr(self.client, "default_voice", "configured"), speed=speed,
                  sentence_id=sentence_id, text=text, status="started")
        try:
            mark_tts_handoff(request_id, sentence_id, speed)
            audio = await self.client.synthesize(
                text,
                getattr(self.client, "default_voice", None),
                getattr(self.client, "default_model", None),
                speed,
            )
            log_event("tts_request", request_id=request_id, sentence_id=sentence_id, status="audio_received")
            await self._deliver(request_id, sentence_id, audio, "generated")
        except asyncio.CancelledError:
            log_event("tts_request", request_id=request_id, sentence_id=sentence_id, status="cancelled")
            raise
        except Exception:
            log_event("tts_request", request_id=request_id, sentence_id=sentence_id, status="failed")
            return

    async def _deliver(self, request_id: int, sentence_id: str | None,
                       audio: bytes, source: str) -> None:
        async with self._lock:
            current_generation = self._generation
        current_state = await self.store.read()
        if request_id != current_generation or current_state.current_sentence_id != sentence_id:
            log_event("tts_request", request_id=request_id, sentence_id=sentence_id, status="discarded")
            return
        await self.controller.mark_spoken(sentence_id or "")
        await self.controller.set_playing(True)
        await self.playback.play(audio, request_id)
        log_event("tts_request", request_id=request_id, sentence_id=sentence_id,
                  status="played", source=source)

    async def _schedule_prefetch(self, request_id: int, sentence_id: str, speed: float) -> None:
        next_sentence = await self.store.sentence_after(sentence_id)
        if not next_sentence:
            return
        text = await self._speech_text(
            next_sentence,
            include_section=next_sentence.boundary_before == "section",
        )
        async with self._lock:
            if request_id != self._generation:
                return
            self._prefetch_target = (next_sentence.id, speed)
            self._prefetch_task = asyncio.create_task(self._prefetch(
                request_id, next_sentence.id, text, speed,
            ))

    async def _speech_text(self, sentence: Sentence, include_section: bool) -> str:
        if not include_section:
            return sentence.normalized_text
        context = await self.store.section_context(sentence.id)
        if not context:
            return sentence.normalized_text
        section_number, title = context
        announcement = f"Section {section_number}."
        if title:
            announcement += f" {normalize_text(title).rstrip('.')}."
        return f"{announcement} {sentence.normalized_text}"

    async def _prefetch(self, generation: int, sentence_id: str,
                        text: str, speed: float) -> None:
        log_event("tts_prefetch", sentence_id=sentence_id, speed=speed, status="started")
        try:
            mark_tts_handoff(None, sentence_id, speed)
            audio = await self.client.synthesize(
                text,
                getattr(self.client, "default_voice", None),
                getattr(self.client, "default_model", None),
                speed,
            )
            async with self._lock:
                if generation != self._generation or self._prefetch_target != (sentence_id, speed):
                    log_event("tts_prefetch", sentence_id=sentence_id, status="discarded")
                    return
                self._prefetched = (sentence_id, speed, audio)
            log_event("tts_prefetch", sentence_id=sentence_id, status="ready")
        except asyncio.CancelledError:
            log_event("tts_prefetch", sentence_id=sentence_id, status="cancelled")
            raise
        except Exception:
            log_event("tts_prefetch", sentence_id=sentence_id, status="failed")

