import logging

from fastapi import FastAPI

from backend.api.command_routes import router as command_router
from backend.api.document_routes import router as document_router
from backend.api.playback_routes import router as playback_router
from backend.service import ReaderService


def create_app(reader: ReaderService | None = None) -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    app = FastAPI(title="Voice Document Reader", version="0.1.0")
    app.state.reader = reader or ReaderService()
    from backend.voice.asr import FasterWhisperRecognizer
    app.state.reader.recognizer = FasterWhisperRecognizer()
    app.include_router(document_router)
    app.include_router(command_router)
    app.include_router(playback_router)
    return app


app = create_app()
