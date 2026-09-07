import json

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
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer test-key"
        assert payload["text"]
        assert payload["speaker"] == "lyra"
        assert payload["modelId"] == "coda"
        assert payload["speedAlpha"] == 1.0
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
async def test_client_completion_renders_next_sentence():
    client = RimeClient(
        api_url="https://test/v1/rime-tts", api_key="test-key", model="coda", voice="lyra",
        transport=mock_transport(),
    )
    service = ReaderService(client=client)
    await service.add_document(structure_document("sample.txt", "First sentence. Second sentence."))
    await service.start()
    assert (await service.store.read()).current_sentence_id == "sec_1.sent_1"
    first_request_id = service.playback.request_id()
    assert first_request_id is not None
    assert (await service.store.read()).current_sentence_id == "sec_1.sent_1"

    await service.complete_playback("sec_1.sent_1", first_request_id)
    assert (await service.store.read()).current_sentence_id == "sec_1.sent_2"
    assert service.playback.request_id() != first_request_id


@pytest.mark.asyncio
async def test_final_completion_resets_cursor_and_play_restarts_document():
    client = RimeClient(
        api_url="https://test/v1/rime-tts", api_key="test-key", model="coda", voice="lyra",
        transport=mock_transport(),
    )
    service = ReaderService(client=client)
    await service.add_document(structure_document("sample.txt", "Only sentence."))
    await service.start()
    final_request_id = service.playback.request_id()

    completed = await service.complete_playback("sec_1.sent_1", final_request_id or 0)

    assert completed.current_sentence_id == "sec_1.sent_1"
    assert completed.document_completed is True
    assert completed.is_playing is False
    assert service.playback.request_id() is None
    assert service.playback.has_audio() is False

    await service.start()
    restarted = await service.store.read()
    assert restarted.current_sentence_id == "sec_1.sent_1"
    assert restarted.document_completed is False
    assert restarted.is_playing is True
    assert service.playback.request_id() is not None


@pytest.mark.asyncio
async def test_unavailable_navigation_does_not_resynthesize_current_sentence():
    client = RimeClient(
        api_url="https://test/v1/rime-tts", api_key="test-key", model="coda", voice="lyra",
        transport=mock_transport(),
    )
    service = ReaderService(client=client)
    await service.add_document(structure_document("sample.txt", "Only sentence."))
    await service.start()

    state = await service.command(CommandIntent.NEXT_SECTION)

    assert state.current_sentence_id == "sec_1.sent_1"
    assert state.is_playing is False
    assert service.playback.request_id() is None
    assert service.playback.has_audio() is False


@pytest.mark.asyncio
async def test_stale_client_completion_is_rejected():
    client = RimeClient(
        api_url="https://test/v1/rime-tts", api_key="test-key", model="coda", voice="lyra",
        transport=mock_transport(),
    )
    service = ReaderService(client=client)
    await service.add_document(structure_document("sample.txt", "First sentence. Second sentence."))
    await service.start()
    stale_request_id = service.playback.request_id()

    await service.command(CommandIntent.SKIP)

    with pytest.raises(ValueError, match="no longer current"):
        await service.complete_playback("sec_1.sent_1", stale_request_id or 0)


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
