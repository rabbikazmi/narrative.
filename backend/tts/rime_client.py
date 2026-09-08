import os
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


class RimeClient:
    """Small async adapter for Rime; navigation state never enters this class."""

    def __init__(self, api_url: str | None = None, api_key: str | None = None,
                 model: str | None = None, voice: str | None = None,
                 language: str | None = None,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.api_url = api_url or os.getenv("RIME_API_URL", "https://users.rime.ai/v1/rime-tts")
        self.api_key = api_key or os.getenv("RIME_API_KEY")
        self.default_model = model or os.getenv("RIME_MODEL_ID", os.getenv("RIME_MODEL", ""))
        self.default_voice = voice or os.getenv("RIME_VOICE", os.getenv("RIME_SPEAKER", ""))
        self.default_language = language or os.getenv("RIME_LANGUAGE", "en")
        self.transport = transport

    def _request(self, text: str, voice: str | None, model: str | None, speed: float) -> tuple[dict, dict]:
        if not text.strip():
            raise ValueError("TTS input cannot be empty")
        if not self.api_key:
            raise RuntimeError("RIME_API_KEY is not configured")
        selected_voice = voice or self.default_voice
        selected_model = model or self.default_model
        if not selected_voice or not selected_model:
            raise RuntimeError("RIME voice and model are not configured")
        return (
            {"Authorization": f"Bearer {self.api_key}", "Accept": "audio/wav"},
            {
                "text": text,
                "speaker": selected_voice,
                "modelId": selected_model,
                "language": self.default_language,
                "speedAlpha": speed,
            },
        )

    async def synthesize(self, text: str, voice: str | None = None,
                         model: str | None = None, speed: float = 1.0) -> bytes:
        headers, payload = self._request(text, voice, model, speed)
        try:
            async with httpx.AsyncClient(timeout=60, transport=self.transport) as client:
                response = await client.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise RuntimeError("Rime synthesis request failed") from error
        if not response.content:
            raise RuntimeError("Rime returned an empty audio response")
        return response.content

    async def stream(self, text: str, voice: str | None = None,
                     model: str | None = None, speed: float = 1.0) -> AsyncIterator[bytes]:
        headers, payload = self._request(text, voice, model, speed)
        try:
            async with httpx.AsyncClient(timeout=60, transport=self.transport) as client:
                async with client.stream("POST", self.api_url, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    received = False
                    async for chunk in response.aiter_bytes():
                        received = True
                        yield chunk
                    if not received:
                        raise RuntimeError("Rime returned an empty audio response")
        except httpx.HTTPError as error:
            raise RuntimeError("Rime streaming request failed") from error
