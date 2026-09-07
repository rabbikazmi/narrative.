from io import BytesIO

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.playback.manager import PlaybackManager
from backend.service import ReaderService
from backend.tts.rime_client import RimeClient


class MockRimeClient(RimeClient):
    async def synthesize(self, text, voice=None, model=None, speed=1.0):
        return b"test-audio"


class BrowserPlayback(PlaybackManager):
    async def play(self, audio, request_id):
        self._audio = audio
        self._request_id = request_id
        self._playing = True


def test_final_api_completion_resets_document_to_start():
    app = create_app(ReaderService(client=MockRimeClient(), playback=BrowserPlayback()))
    with TestClient(app) as client:
        uploaded = client.post(
            "/documents/upload",
            files={"file": ("sample.txt", BytesIO(b"First sentence. Second sentence."), "text/plain")},
        )
        assert uploaded.status_code == 200

        first = client.post("/playback/start").json()
        second = client.post(
            "/playback/complete",
            json={"sentence_id": "sec_1.sent_1", "request_id": first["request_id"]},
        ).json()
        finished = client.post(
            "/playback/complete",
            json={"sentence_id": "sec_1.sent_2", "request_id": second["request_id"]},
        )

        assert finished.status_code == 200
        assert finished.json()["document_completed"] is True
        assert finished.json()["current_sentence_id"] == "sec_1.sent_1"
        assert finished.json()["request_id"] is None
