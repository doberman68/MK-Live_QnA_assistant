"""Auto-mode question detection and manual trigger logic."""
from __future__ import annotations

import asyncio
import json
from typing import Awaitable, Callable, Optional, Tuple

from config import AppConfig
from llm.base import LLMProvider
from transcript import TranscriptBuffer

DETECT_PROMPT = (
    "You are analyzing a live meeting transcript excerpt.\n"
    "Determine whether the speaker just asked a question that needs an answer.\n"
    "Reply with JSON ONLY — no extra text:\n"
    '{"is_question": true/false, "question_text": "<extracted question or null>"}'
)

ANSWER_PROMPT = (
    "You are a helpful meeting assistant. "
    "A question was asked during a meeting. "
    "Use the transcript context below to answer it concisely and accurately. "
    "If the transcript does not contain enough context, say so briefly.\n\n"
    "Meeting transcript:\n"
)


class QuestionDetector:
    def __init__(
        self,
        llm: LLMProvider,
        buffer: TranscriptBuffer,
        config: AppConfig,
        on_answer: Callable[[str, str], Awaitable[None]],
    ):
        self._llm = llm
        self._buffer = buffer
        self._config = config
        self._on_answer = on_answer
        self._last_checked_ts: float = 0.0
        self._task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Auto mode
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._detection_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _detection_loop(self) -> None:
        while True:
            await asyncio.sleep(self._config.auto_check_interval_seconds)
            try:
                await self._check_for_question()
            except Exception:
                pass  # never let detection errors crash the loop

    async def _check_for_question(self) -> None:
        new_segments = self._buffer.get_since(self._last_checked_ts)
        if not new_segments:
            return

        self._last_checked_ts = new_segments[-1].timestamp
        chunk_text = self._buffer.to_text(new_segments)

        raw = await self._llm.chat(DETECT_PROMPT, chunk_text)
        result = _parse_detect(raw)
        if not result.get("is_question"):
            return

        question = result.get("question_text") or chunk_text
        full_context = self._buffer.to_text(self._buffer.get_all())
        answer = await self._llm.chat(ANSWER_PROMPT + full_context, question)
        await self._on_answer(question, answer)

    # ------------------------------------------------------------------
    # Manual mode
    # ------------------------------------------------------------------

    async def manual_trigger(self, lookback_seconds: int) -> Tuple[str, str]:
        segments = self._buffer.get_last_n_seconds(lookback_seconds)
        if not segments:
            return "No recent audio", "There is no transcript to analyze yet."

        chunk_text = self._buffer.to_text(segments)
        raw = await self._llm.chat(DETECT_PROMPT, chunk_text)
        result = _parse_detect(raw)
        question = result.get("question_text") or chunk_text

        full_context = self._buffer.to_text(self._buffer.get_all())
        answer = await self._llm.chat(ANSWER_PROMPT + full_context, question)
        return question, answer


def _parse_detect(raw: str) -> dict:
    """Extract JSON from LLM response, tolerating markdown code fences."""
    text = raw.strip()
    # Strip ```json ... ``` wrappers if present
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except Exception:
        return {"is_question": False, "question_text": None}
