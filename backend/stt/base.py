from abc import ABC, abstractmethod


class STTProvider(ABC):
    @abstractmethod
    async def initialize(self) -> None:
        """Load models or validate API credentials."""

    @abstractmethod
    async def transcribe(self, audio_data: bytes, sample_rate: int) -> str:
        """Transcribe raw PCM int16 bytes to text. Returns empty string on failure."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Release resources."""
