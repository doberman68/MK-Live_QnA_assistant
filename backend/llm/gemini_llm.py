import asyncio

from .base import LLMProvider


class GeminiLLM(LLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        self._api_key = api_key
        self._model_name = model

    async def initialize(self) -> None:
        import google.generativeai as genai
        genai.configure(api_key=self._api_key)

    async def chat(self, system_prompt: str, user_message: str) -> str:
        import google.generativeai as genai

        # google-generativeai SDK is synchronous; run in executor to avoid blocking
        def _generate() -> str:
            model = genai.GenerativeModel(
                model_name=self._model_name,
                system_instruction=system_prompt,
            )
            response = model.generate_content(user_message)
            return response.text

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _generate)

    async def shutdown(self) -> None:
        pass
