import io
import struct
import wave

from .base import STTProvider


class WhisperAPISTT(STTProvider):
    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = None

    async def initialize(self) -> None:
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=self._api_key)

    async def transcribe(self, audio_data: bytes, sample_rate: int) -> str:
        if not self._client:
            return ""

        # Wrap raw PCM int16 bytes in a WAV container for the API
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data)
        wav_buffer.seek(0)

        transcript = await self._client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.wav", wav_buffer, "audio/wav"),
        )
        return transcript.text.strip()

    async def shutdown(self) -> None:
        if self._client:
            await self._client.close()
        self._client = None
