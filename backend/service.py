from backend.models.commands import CommandIntent
from backend.models.document import Document
from backend.navigation.controller import NavigationController
from backend.navigation.state import NavigationStateStore
from backend.playback.manager import PlaybackManager
from backend.tts.request_manager import RequestManager
from backend.utils.logger import log_event


class ReaderService:
    def __init__(self) -> None:
        self.documents: dict[str, Document] = {}
        self.store = NavigationStateStore()
        self.controller = NavigationController(self.store)
        self.playback = PlaybackManager()
        from backend.tts.rime_client import RimeClient
        self.requests = RequestManager(self.store, self.controller, RimeClient(), self.playback)

    async def add_document(self, document: Document) -> Document:
        self.documents[document.id] = document
        await self.store.load_document(document)
        return document

    async def command(self, intent: CommandIntent) -> None:
        log_event("command_received", intent=intent.value)
        await self.requests.interrupt()
        await self.controller.apply(intent)
        if intent in {
            CommandIntent.NEXT_SECTION,
            CommandIntent.PREVIOUS_SECTION,
            CommandIntent.SKIP,
            CommandIntent.REPEAT,
            CommandIntent.SLOW_DOWN,
            CommandIntent.SPEED_UP,
            CommandIntent.READ_NUMBERS,
            CommandIntent.RESUME,
        }:
            await self.requests.render_current(numbers_only=intent == CommandIntent.READ_NUMBERS)

    async def start(self) -> None:
        await self.command(CommandIntent.RESUME)
