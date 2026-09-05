from backend.utils.logger import log_event


class PlaybackManager:
    def __init__(self) -> None:
        self._audio: bytes | None = None
        self._playing = False
        self._request_id: int | None = None

    async def play(self, audio: bytes, request_id: int) -> None:
        self._audio = audio
        self._request_id = request_id
        self._playing = True
        log_event("playback_started", request_id=request_id)

    async def pause(self) -> None:
        self._playing = False
        log_event("playback_paused", request_id=self._request_id)

    async def resume(self) -> None:
        if self._audio:
            self._playing = True
            log_event("playback_resumed", request_id=self._request_id)

    async def complete(self, request_id: int) -> bool:
        if request_id != self._request_id:
            return False
        self._playing = False
        log_event("natural_completion", request_id=request_id)
        return True

    async def stop(self) -> None:
        self._playing = False

    async def flush(self) -> None:
        await self.stop()
        self._audio = None
        self._request_id = None
        log_event("playback_interruption")

    def is_playing(self) -> bool:
        return self._playing

    def has_audio(self) -> bool:
        return self._audio is not None

    def request_id(self) -> int | None:
        return self._request_id

    async def audio_stream(self):
        if self._audio:
            yield self._audio
