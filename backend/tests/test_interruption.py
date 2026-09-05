import asyncio

import pytest

from backend.document.structure import structure_document
from backend.models.commands import CommandIntent
from backend.navigation.controller import NavigationController
from backend.navigation.state import NavigationStateStore
from backend.playback.manager import PlaybackManager
from backend.tts.request_manager import RequestManager


class DelayedClient:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def synthesize(self, text, voice, model, speed):
        self.started.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            await self.release.wait()
        return text.encode()


@pytest.mark.asyncio
async def test_late_tts_response_is_discarded_after_new_command():
    store = NavigationStateStore()
    await store.load_document(structure_document("x.txt", "First sentence.\n\nSecond sentence."))
    controller = NavigationController(store)
    playback = PlaybackManager()
    client = DelayedClient()
    manager = RequestManager(store, controller, client, playback)

    first = asyncio.create_task(manager.render_current())
    await client.started.wait()
    await manager.interrupt()
    await controller.apply(CommandIntent.NEXT_SECTION)
    client.release.set()
    await first
    assert not playback.is_playing()
