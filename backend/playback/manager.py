import asyncio

from backend.utils.logger import log_event


class PlaybackManager:
    def __init__(self) -> None:
        self._audio: bytes | None = None
        self._playing = False
        self._playback_task: asyncio.Task[None] | None = None

    async def play(self, audio: bytes, request_id: int, on_complete) -> None:
        await self.stop()
        self._audio = audio
        self._playing = True
        log_event("playback_started", request_id=request_id)
        self._playback_task = asyncio.create_task(self._complete(request_id, on_complete))

    async def _complete(self, request_id: int, on_complete) -> None:
        try:
            while not self._playing:
                await asyncio.sleep(0.01)
            await asyncio.sleep(0)
            self._playing = False
            log_event("natural_completion", request_id=request_id)
            await on_complete()
        except asyncio.CancelledError:
            return

    async def pause(self) -> None:
        self._playing = False
        log_event("playback_paused")

    async def resume(self) -> None:
        if self._audio:
            self._playing = True
            log_event("playback_resumed")

    async def stop(self) -> None:
        if self._playback_task and not self._playback_task.done():
            self._playback_task.cancel()
        self._playback_task = None
        self._playing = False

    async def flush(self) -> None:
        await self.stop()
        self._audio = None
        log_event("playback_interruption")

    def is_playing(self) -> bool:
        return self._playing

    def has_audio(self) -> bool:
        return self._audio is not None

    async def audio_stream(self):
        if self._audio:
            yield self._audio
