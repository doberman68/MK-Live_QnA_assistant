from .base import LLMProvider


class AnthropicLLM(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        self._api_key = api_key
        self._model = model
        self._client = None

    async def initialize(self) -> None:
        import anthropic
        self._client = anthropic.AsyncAnthropic(api_key=self._api_key)

    async def chat(self, system_prompt: str, user_message: str) -> str:
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return message.content[0].text

    async def shutdown(self) -> None:
        if self._client:
            await self._client.close()
        self._client = None
