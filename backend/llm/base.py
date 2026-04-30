from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def initialize(self) -> None:
        """Validate credentials and prepare the provider."""

    @abstractmethod
    async def chat(self, system_prompt: str, user_message: str) -> str:
        """Single-turn chat. Returns the assistant text response."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Release resources."""
