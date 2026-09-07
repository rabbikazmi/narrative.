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
        if intent == CommandIntent.STOP:
            return await self.stop()

        previous = await self.store.read()
        await self.requests.interrupt()
        state = await self.controller.apply(intent)
        navigation_intents = {
            CommandIntent.NEXT_SECTION,
            CommandIntent.PREVIOUS_SECTION,
            CommandIntent.PREVIOUS_SENTENCE,
            CommandIntent.SKIP,
        }
        if intent in navigation_intents and state.current_sentence_id == previous.current_sentence_id:
            return await self.controller.set_playing(False)
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
            suppress_section_announcement = intent in {
                CommandIntent.REPEAT,
                CommandIntent.SLOW_DOWN,
                CommandIntent.SPEED_UP,
                CommandIntent.READ_NUMBERS,
            }
            await self.requests.render_current(
                numbers_only=intent == CommandIntent.READ_NUMBERS,
                announce_section=False if suppress_section_announcement else None,
            )
        return state

    async def start(self) -> None:
        await self.command(CommandIntent.RESUME)

    async def stop(self) -> NavigationState:
        await self.requests.interrupt()
        return await self.controller.apply(CommandIntent.PAUSE)

    async def complete_playback(self, sentence_id: str, request_id: int) -> NavigationState:
        state = await self.store.read()
        if state.current_sentence_id != sentence_id:
            raise ValueError("The completed sentence is no longer current")
        if not await self.playback.complete(request_id):
            raise ValueError("The completed audio request is no longer current")

        await self.controller.set_playing(False)
        updated = await self.controller.advance_after_completion(sentence_id)
        if updated.document_completed:
            await self.playback.flush()
            log_event("document_completed", document_id=updated.document_id)
            return await self.store.read()
        if updated.current_sentence_id and updated.current_sentence_id != sentence_id:
            log_event("navigation_advanced", sentence_id=updated.current_sentence_id)
            await self.requests.render_current()
        return await self.store.read()
