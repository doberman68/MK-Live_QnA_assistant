import asyncio
import io
import tempfile
from pathlib import Path

import numpy as np

from .base import STTProvider


class LocalWhisperSTT(STTProvider):
    def __init__(self, model_size: str = "base"):
        self._model_size = model_size
        self._model = None

    async def initialize(self) -> None:
        import whisper
        loop = asyncio.get_event_loop()
        self._model = await loop.run_in_executor(None, whisper.load_model, self._model_size)

    async def transcribe(self, audio_data: bytes, sample_rate: int) -> str:
        if self._model is None:
            return ""

        import whisper

        # Convert int16 PCM bytes → float32 numpy array normalised to [-1, 1]
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        # Whisper expects 16 kHz mono; resample if needed (basic nearest-neighbour)
        if sample_rate != 16000:
            ratio = 16000 / sample_rate
            new_len = int(len(audio_np) * ratio)
            indices = np.round(np.linspace(0, len(audio_np) - 1, new_len)).astype(int)
            audio_np = audio_np[indices]

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._model.transcribe(audio_np, fp16=False)
        )
        return result.get("text", "").strip()

    async def shutdown(self) -> None:
        self._model = None
