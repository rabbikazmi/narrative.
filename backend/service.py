from backend.models.commands import CommandIntent
from backend.models.document import Document
from backend.models.navigation import NavigationState
from backend.navigation.controller import NavigationController
from backend.navigation.state import NavigationStateStore
from backend.playback.manager import PlaybackManager
from backend.tts.rime_client import RimeClient
from backend.tts.request_manager import RequestManager
from backend.utils.logger import log_event


class ReaderService:
    def __init__(self, client: RimeClient | None = None,
                 playback: PlaybackManager | None = None) -> None:
        self.documents: dict[str, Document] = {}
        self.store = NavigationStateStore()
        self.controller = NavigationController(self.store)
        self.playback = playback or PlaybackManager()
        self.client = client or RimeClient()
        self.requests = RequestManager(
            self.store, self.controller, self.client, self.playback,
            on_natural_completion=self._render_after_completion,
        )

    async def add_document(self, document: Document) -> Document:
        await self.requests.interrupt()
        self.documents[document.id] = document
        await self.store.load_document(document)
        return document

    async def command(self, intent: CommandIntent) -> NavigationState:
        log_event("command_received", intent=intent.value)
        if intent == CommandIntent.PAUSE:
            await self.playback.pause()
            return await self.controller.apply(intent)
        if intent == CommandIntent.RESUME:
            state = await self.controller.apply(intent)
            if self.playback.has_audio():
                await self.playback.resume()
            else:
                await self.requests.render_current()
            return state

        await self.requests.interrupt()
        state = await self.controller.apply(intent)
        if intent in {
            CommandIntent.NEXT_SECTION,
            CommandIntent.PREVIOUS_SECTION,
            CommandIntent.PREVIOUS_SENTENCE,
            CommandIntent.SKIP,
            CommandIntent.REPEAT,
            CommandIntent.SLOW_DOWN,
            CommandIntent.SPEED_UP,
            CommandIntent.READ_NUMBERS,
        }:
            await self.requests.render_current(numbers_only=intent == CommandIntent.READ_NUMBERS)
        return state

    async def start(self) -> None:
        await self.command(CommandIntent.RESUME)

    async def stop(self) -> NavigationState:
        await self.requests.interrupt()
        return await self.controller.apply(CommandIntent.PAUSE)

    async def _render_after_completion(self, sentence_id: str, state: NavigationState) -> None:
        if state.current_sentence_id and state.current_sentence_id != sentence_id:
            log_event("navigation_advanced", sentence_id=state.current_sentence_id)
            await self.requests.render_current()
