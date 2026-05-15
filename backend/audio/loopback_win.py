"""Windows WASAPI loopback capture using pyaudiowpatch."""
from __future__ import annotations

import asyncio
from typing import Callable, List, Optional


class WindowsLoopbackCapture:
    CHUNK = 1024
    CHANNELS = 1
    RATE = 16000

    def __init__(
        self,
        device_index: Optional[int] = None,
        callback: Optional[Callable[[bytes], None]] = None,
    ):
        self._device_index = device_index
        self._callback = callback
        self._pa = None
        self._stream = None

    def list_loopback_devices(self) -> List[dict]:
        import pyaudiowpatch as pyaudio

        pa = pyaudio.PyAudio()
        devices = []
        try:
            for i in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(i)
                if info.get("isLoopbackDevice"):
                    devices.append({
                        "index": i,
                        "name": info["name"],
                        "sample_rate": int(info["defaultSampleRate"]),
                    })
        finally:
            pa.terminate()
        return devices

    def _find_default_loopback(self, pa) -> Optional[dict]:
        """Return the first WASAPI loopback device info, or None."""
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get("isLoopbackDevice"):
                if self._device_index is None or i == self._device_index:
                    return info
        return None

    def start(self) -> None:
        import pyaudiowpatch as pyaudio

        self._pa = pyaudio.PyAudio()
        device_info = self._find_default_loopback(self._pa)
        if device_info is None:
            self._pa.terminate()
            raise RuntimeError("No WASAPI loopback device found.")

        device_idx = int(device_info["index"])
        src_rate = int(device_info["defaultSampleRate"])

        def _stream_callback(in_data, frame_count, time_info, status):
            if self._callback and in_data:
                self._callback(in_data, src_rate)
            return (None, pyaudio.paContinue)

        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=self._CHANNELS_for_device(device_info),
            rate=src_rate,
            input=True,
            input_device_index=device_idx,
            frames_per_buffer=self.CHUNK,
            stream_callback=_stream_callback,
        )
        self._stream.start_stream()

    def _CHANNELS_for_device(self, info: dict) -> int:
        ch = int(info.get("maxInputChannels", 1))
        return max(1, min(ch, 2))

    def stop(self) -> None:
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._pa:
            self._pa.terminate()
            self._pa = None
