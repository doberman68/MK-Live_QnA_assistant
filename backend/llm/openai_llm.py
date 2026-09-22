from .base import LLMProvider


class OpenAILLM(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self._api_key = api_key
        self._model = model
        self._client = None

    async def initialize(self) -> None:
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=self._api_key)

    async def chat(self, system_prompt: str, user_message: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content or ""

    async def shutdown(self) -> None:
        if self._client:
            await self._client.close()
        self._client = None
