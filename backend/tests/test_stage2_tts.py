import asyncio

import httpx
import pytest

from backend.document.structure import structure_document
from backend.models.commands import CommandIntent
from backend.playback.manager import PlaybackManager
from backend.service import ReaderService
from backend.tts.rime_client import RimeClient


def mock_transport(audio: bytes = b"wav-audio") -> httpx.MockTransport:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/rime-tts"
        payload = httpx.Request.content
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(200, content=audio, headers={"content-type": "audio/wav"})

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_rime_client_synthesizes_with_configured_request():
    client = RimeClient(
        api_url="https://test/v1/rime-tts",
        api_key="test-key",
        model="coda",
        voice="lyra",
        transport=mock_transport(),
    )
    audio = await client.synthesize("The method achieved ninety-seven percent accuracy.", speed=1.0)
    assert audio == b"wav-audio"


@pytest.mark.asyncio
async def test_natural_completion_renders_next_sentence():
    client = RimeClient(
        api_url="https://test/v1/rime-tts", api_key="test-key", model="coda", voice="lyra",
        transport=mock_transport(),
    )
    service = ReaderService(client=client)
    await service.add_document(structure_document("sample.txt", "First sentence. Second sentence."))
    await service.start()
    assert (await service.store.read()).current_sentence_id == "sec_1.sent_1"
    await asyncio.sleep(0.05)
    assert (await service.store.read()).current_sentence_id == "sec_1.sent_2"


@pytest.mark.asyncio
async def test_pause_resume_preserves_current_sentence():
    client = RimeClient(
        api_url="https://test/v1/rime-tts", api_key="test-key", model="coda", voice="lyra",
        transport=mock_transport(),
    )
    service = ReaderService(client=client)
    await service.add_document(structure_document("sample.txt", "Only sentence."))
    await service.start()
    await service.command(CommandIntent.PAUSE)
    paused = await service.store.read()
    assert paused.current_sentence_id == "sec_1.sent_1"
    assert paused.is_playing is False
    await service.command(CommandIntent.RESUME)
    assert (await service.store.read()).current_sentence_id == "sec_1.sent_1"


@pytest.mark.asyncio
async def test_missing_rime_key_is_a_handled_synthesis_failure():
    client = RimeClient(api_key=None, model="coda", voice="lyra")
    client.api_key = None
    with pytest.raises(RuntimeError, match="RIME_API_KEY"):
        await client.synthesize("A sentence")
