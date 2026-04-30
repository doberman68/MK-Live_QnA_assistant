from typing import List

import httpx

from .base import LLMProvider


class OllamaLLM(LLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3"):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client: httpx.AsyncClient = None

    async def initialize(self) -> None:
        self._client = httpx.AsyncClient(timeout=120.0)

    async def chat(self, system_prompt: str, user_message: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
        }
        response = await self._client.post(f"{self._base_url}/api/chat", json=payload)
        response.raise_for_status()
        return response.json()["message"]["content"]

    async def list_models(self) -> List[str]:
        try:
            response = await self._client.get(f"{self._base_url}/api/tags")
            response.raise_for_status()
            return [m["name"] for m in response.json().get("models", [])]
        except Exception:
            return []

    async def shutdown(self) -> None:
        if self._client:
            await self._client.aclose()
        self._client = None
