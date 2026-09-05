import os
from collections.abc import AsyncIterator

import httpx


class RimeClient:
    """Small async adapter for Rime; navigation state never enters this class."""

    def __init__(self, api_url: str | None = None, api_key: str | None = None) -> None:
        self.api_url = api_url or os.getenv("RIME_API_URL", "https://api.rime.ai/v1/rime-tts")
        self.api_key = api_key or os.getenv("RIME_API_KEY")

    async def synthesize(self, text: str, voice: str, model: str, speed: float) -> bytes:
        if not self.api_key:
            return f"local-audio:{model}:{voice}:{speed}:{text}".encode()
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"text": text, "speaker": voice, "modelId": model, "speedAlpha": speed}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            return response.content

    async def stream(self, text: str, voice: str, model: str, speed: float) -> AsyncIterator[bytes]:
        if not self.api_key:
            yield await self.synthesize(text, voice, model, speed)
            return
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"text": text, "speaker": voice, "modelId": model, "speedAlpha": speed}
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream("POST", self.api_url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk
