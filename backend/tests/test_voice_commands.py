from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.playback.manager import PlaybackManager
from backend.service import ReaderService
from backend.tts.rime_client import RimeClient
from backend.voice.asr import FasterWhisperRecognizer


class MockRimeClient(RimeClient):
    async def synthesize(self, text, voice=None, model=None, speed=1.0):
        return b"test-audio"


class NoCompletionPlayback(PlaybackManager):
    async def play(self, audio, request_id):
        self._audio = audio
        self._request_id = request_id
        self._playing = True


class FakeRecognizer:
    def __init__(self, transcript="next section", error=None):
        self.transcript = transcript
        self.error = error
        self.received = None

    async def transcribe(self, audio, filename=None):
        self.received = (audio, filename)
        if self.error:
            raise self.error
        return self.transcript


def make_client(recognizer):
    reader = ReaderService(client=MockRimeClient(), playback=NoCompletionPlayback())
    return TestClient(create_app(reader, recognizer=recognizer))


def upload_document(client):
    response = client.post(
        "/documents/upload",
        files={
            "file": (
                "voice.txt",
                BytesIO(b"First section\n\nFirst sentence.\n\nSecond section\n\nSecond sentence."),
                "text/plain",
            )
        },
    )
    assert response.status_code == 200


def test_voice_command_transcribes_and_returns_updated_playback_state():
    recognizer = FakeRecognizer()
    with make_client(recognizer) as client:
        upload_document(client)
        response = client.post(
            "/command/voice",
            files={"audio": ("command.webm", BytesIO(b"recorded-audio"), "audio/webm")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert recognizer.received == (b"recorded-audio", "command.webm")
    assert payload["transcript"] == "next section"
    assert payload["intent"] == "NEXT_SECTION"
    assert payload["state"]["current_section_id"] == "sec_2"
    assert payload["request_id"] is not None


def test_start_voice_command_begins_playback_without_using_play_button():
    with make_client(FakeRecognizer(transcript="start reading")) as client:
        upload_document(client)
        response = client.post(
            "/command/voice",
            files={"audio": ("command.webm", BytesIO(b"recorded-audio"), "audio/webm")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "RESUME"
    assert payload["state"]["is_playing"] is True
    assert payload["request_id"] is not None


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (ValueError("No speech was recognized."), 422),
        (RuntimeError("Voice recognition is unavailable."), 503),
    ],
)
def test_voice_command_reports_recognition_errors(error, status_code):
    with make_client(FakeRecognizer(error=error)) as client:
        response = client.post(
            "/command/voice",
            files={"audio": ("command.webm", BytesIO(b"audio"), "audio/webm")},
        )

    assert response.status_code == status_code
    assert response.json()["detail"] == str(error)


@pytest.mark.asyncio
async def test_faster_whisper_adapter_decodes_injected_model_and_removes_temp_file():
    seen_path = None

    class FakeModel:
        def transcribe(self, path, **options):
            nonlocal seen_path
            seen_path = path
            assert Path(path).read_bytes() == b"webm-audio"
            assert options["vad_filter"] is True
            assert "pause" in options["hotwords"]
            return iter([SimpleNamespace(text=" pause ")]), SimpleNamespace()

    recognizer = FasterWhisperRecognizer()
    recognizer._model = FakeModel()
    transcript = await recognizer.transcribe(b"webm-audio", "command.webm")

    assert transcript == "pause"
    assert seen_path is not None
    assert not Path(seen_path).exists()
