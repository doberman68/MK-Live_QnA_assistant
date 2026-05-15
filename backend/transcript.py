import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import List


@dataclass
class TranscriptSegment:
    text: str
    timestamp: float = field(default_factory=time.time)
    source: str = "mic"  # "mic" | "loopback"


class TranscriptBuffer:
    def __init__(self, max_age_seconds: int = 300):
        self._segments: deque[TranscriptSegment] = deque()
        self._max_age = max_age_seconds
        self._lock = asyncio.Lock()

    def _prune(self) -> None:
        cutoff = time.time() - self._max_age
        while self._segments and self._segments[0].timestamp < cutoff:
            self._segments.popleft()

    def add_segment(self, text: str, source: str = "mic") -> None:
        self._prune()
        self._segments.append(TranscriptSegment(text=text, source=source))

    def get_last_n_seconds(self, seconds: int) -> List[TranscriptSegment]:
        self._prune()
        cutoff = time.time() - seconds
        return [s for s in self._segments if s.timestamp >= cutoff]

    def get_all(self) -> List[TranscriptSegment]:
        self._prune()
        return list(self._segments)

    def get_since(self, timestamp: float) -> List[TranscriptSegment]:
        return [s for s in self._segments if s.timestamp > timestamp]

    def to_text(self, segments: List[TranscriptSegment]) -> str:
        return "\n".join(s.text for s in segments)

    def clear(self) -> None:
        self._segments.clear()
