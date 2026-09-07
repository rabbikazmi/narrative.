from io import BytesIO

import fitz
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.service import ReaderService
from backend.playback.manager import PlaybackManager
from backend.tts.rime_client import RimeClient


class MockRimeClient(RimeClient):
    async def synthesize(self, text, voice=None, model=None, speed=1.0):
        return b"test-audio"


class NoCompletionPlayback(PlaybackManager):
    async def play(self, audio, request_id):
        self._audio = audio
        self._request_id = request_id
        self._playing = True


def upload(client: TestClient, filename: str, content: bytes):
    response = client.post(
        "/documents/upload",
        files={"file": (filename, BytesIO(content), "text/plain")},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_txt_document_navigates_end_to_end():
    app = create_app(ReaderService(client=MockRimeClient(), playback=NoCompletionPlayback()))
    with TestClient(app) as client:
        document = upload(
            client,
            "sample.txt",
            b"Section one\n\nThis is sentence one. This is sentence two.\n\n"
            b"Section two\n\nThis is sentence three. This is sentence four.",
        )

        assert document["sections"][0]["sentences"][0]["id"] == "sec_1.sent_1"
        assert document["sections"][1]["sentences"][1]["normalized_text"]
        state = client.get("/playback/state").json()
        assert state["current_sentence_id"] == "sec_1.sent_1"
        assert state["is_playing"] is False

        current = client.get("/playback/current").json()
        assert current["sentence_id"] == "sec_1.sent_1"
        assert current["raw_text"] == "This is sentence one."

        for expected in ("sec_1.sent_2", "sec_2.sent_1", "sec_2.sent_2", "sec_2.sent_2"):
            response = client.post("/command", json={"text": "next sentence"})
            assert response.status_code == 200
            assert response.json()["state"]["current_sentence_id"] == expected

        response = client.post("/command", json={"text": "previous sentence"})
        assert response.json()["state"]["current_sentence_id"] == "sec_2.sent_1"

        response = client.post("/command", json={"text": "previous section"})
        assert response.json()["state"]["current_sentence_id"] == "sec_1.sent_1"

        response = client.post("/command", json={"text": "repeat"})
        assert response.json()["state"]["current_sentence_id"] == "sec_1.sent_1"


def test_markdown_speed_and_playback_state_do_not_move_cursor():
    app = create_app(ReaderService(client=MockRimeClient(), playback=NoCompletionPlayback()))
    with TestClient(app) as client:
        upload(client, "sample.md", b"# Heading\n\nMarkdown sentence.")
        initial = client.get("/playback/state").json()

        assert client.post("/command", json={"text": "faster"}).json()["state"]["playback_speed"] == 1.1
        assert client.post("/playback/pause").json()["is_playing"] is False
        assert client.post("/playback/resume").json()["is_playing"] is True
        spoken_before_stop = client.get("/playback/state").json()["last_spoken_id"]
        stopped = client.post("/playback/stop").json()
        assert stopped["is_playing"] is False
        assert stopped["current_sentence_id"] == initial["current_sentence_id"]
        assert stopped["last_spoken_id"] == spoken_before_stop


def test_playback_advances_only_after_matching_client_completion():
    app = create_app(ReaderService(client=MockRimeClient(), playback=NoCompletionPlayback()))
    with TestClient(app) as client:
        upload(client, "sample.txt", b"First sentence. Second sentence.")
        started = client.post("/playback/start").json()
        request_id = started["request_id"]

        assert request_id is not None
        assert started["current_sentence_id"] == "sec_1.sent_1"

        stale = client.post(
            "/playback/complete",
            json={"sentence_id": "sec_1.sent_1", "request_id": request_id + 1},
        )
        assert stale.status_code == 409
        assert client.get("/playback/state").json()["current_sentence_id"] == "sec_1.sent_1"

        completed = client.post(
            "/playback/complete",
            json={"sentence_id": "sec_1.sent_1", "request_id": request_id},
        )
        assert completed.status_code == 200
        assert completed.json()["current_sentence_id"] == "sec_1.sent_2"
        assert completed.json()["request_id"] != request_id


def test_pdf_upload_and_invalid_uploads():
    app = create_app(ReaderService(client=MockRimeClient(), playback=NoCompletionPlayback()))
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "PDF sentence one. PDF sentence two.")
    second_page = pdf.new_page()
    second_page.insert_text((72, 72), "PDF sentence three.")
    pdf_bytes = pdf.tobytes()
    pdf.close()

    with TestClient(app) as client:
        document = upload(client, "sample.pdf", pdf_bytes)
        assert document["sections"][0]["sentences"][0]["raw_text"] == "PDF sentence one."
        assert document["sections"][0]["sentences"][2]["page_number"] == 2
        assert document["sections"][0]["sentences"][2]["boundary_before"] == "page"

        empty = client.post("/documents/upload", files={"file": ("empty.txt", b"", "text/plain")})
        assert empty.status_code == 400
        unsupported = client.post("/documents/upload", files={"file": ("sample.csv", b"data", "text/csv")})
        assert unsupported.status_code == 400
        missing = client.get("/documents/does-not-exist")
        assert missing.status_code == 404
