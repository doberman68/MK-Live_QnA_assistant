"""Audio capture manager — mic and/or system loopback."""
from __future__ import annotations

import asyncio
import platform
import sys
from typing import Awaitable, Callable, List, Optional

import numpy as np

from config import AppConfig, AudioSourceType

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 8000  # 500 ms at 16 kHz


class AudioCaptureManager:
    def __init__(
        self,
        config: AppConfig,
        audio_callback: Callable[[bytes, str, int], Awaitable[None]],
        loop: asyncio.AbstractEventLoop,
    ):
        # audio_callback(pcm_int16_bytes, source, sample_rate)
        self._config = config
        self._audio_callback = audio_callback
        self._loop = loop
        self._running = False
        self._mic_stream = None
        self._loopback_capture = None

    # ------------------------------------------------------------------
    # Device listing
    # ------------------------------------------------------------------

    def list_input_devices(self) -> List[dict]:
        import sounddevice as sd
        devices = []
        try:
            all_devs = sd.query_devices()
            for i, dev in enumerate(all_devs):
                if dev["max_input_channels"] > 0:
                    devices.append({
                        "index": i,
                        "name": dev["name"],
                        "type": "mic",
                        "sample_rate": int(dev["default_samplerate"]),
                    })
        except Exception:
            pass

        if platform.system() == "Windows":
            try:
                from .loopback_win import WindowsLoopbackCapture
                cap = WindowsLoopbackCapture()
                for dev in cap.list_loopback_devices():
                    dev["type"] = "loopback"
                    devices.append(dev)
            except Exception:
                pass

        return devices

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        source = self._config.audio_source

        if source in (AudioSourceType.MIC, AudioSourceType.BOTH):
            self._start_mic()

        if source in (AudioSourceType.LOOPBACK, AudioSourceType.BOTH):
            self._start_loopback()

    def _start_mic(self) -> None:
        import sounddevice as sd

        def _sd_callback(indata: np.ndarray, frames, time_info, status):
            audio = indata[:, 0].copy()
            pcm = (audio * 32767).astype(np.int16).tobytes()
            asyncio.run_coroutine_threadsafe(
                self._audio_callback(pcm, "mic", SAMPLE_RATE), self._loop
            )

        self._mic_stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=CHUNK_SAMPLES,
            device=self._config.mic_device_index,
            callback=_sd_callback,
        )
        self._mic_stream.start()

    def _start_loopback(self) -> None:
        if platform.system() == "Darwin":
            import sounddevice as sd
            # BlackHole appears as a regular input device on macOS
            def _sd_loopback_callback(indata: np.ndarray, frames, time_info, status):
                audio = indata[:, 0].copy()
                pcm = (audio * 32767).astype(np.int16).tobytes()
                asyncio.run_coroutine_threadsafe(
                    self._audio_callback(pcm, "loopback", SAMPLE_RATE), self._loop
                )

            self._loopback_stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=CHUNK_SAMPLES,
                device=self._config.loopback_device_index,
                callback=_sd_loopback_callback,
            )
            self._loopback_stream.start()

        elif platform.system() == "Windows":
            from .loopback_win import WindowsLoopbackCapture

            def _win_callback(pcm_bytes: bytes, src_rate: int):
                asyncio.run_coroutine_threadsafe(
                    self._audio_callback(pcm_bytes, "loopback", src_rate), self._loop
                )

            self._loopback_capture = WindowsLoopbackCapture(
                device_index=self._config.loopback_device_index,
                callback=_win_callback,
            )
            self._loopback_capture.start()

    async def stop(self) -> None:
        self._running = False
        if self._mic_stream:
            self._mic_stream.stop()
            self._mic_stream.close()
            self._mic_stream = None

        loopback_stream = getattr(self, "_loopback_stream", None)
        if loopback_stream:
            loopback_stream.stop()
            loopback_stream.close()
            self._loopback_stream = None

        if self._loopback_capture:
            self._loopback_capture.stop()
            self._loopback_capture = None
