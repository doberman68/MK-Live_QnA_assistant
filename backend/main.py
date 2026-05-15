"""FastAPI backend for MK-Live Q&A Assistant."""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import List, Optional, Set

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import AppConfig, AppMode, LLMProviderType, STTProviderType, load_config, save_config
from llm.base import LLMProvider
from question_detector import QuestionDetector
from stt.base import STTProvider
from transcript import TranscriptBuffer

# ---------------------------------------------------------------------------
# Global app state
# ---------------------------------------------------------------------------

class _State:
    config: AppConfig = AppConfig()
    stt: Optional[STTProvider] = None
    llm: Optional[LLMProvider] = None
    buffer: TranscriptBuffer = TranscriptBuffer()
    capture = None  # AudioCaptureManager, imported lazily
    detector: Optional[QuestionDetector] = None
    is_capturing: bool = False
    ws_clients: Set[WebSocket] = set()
    # Audio accumulation between STT calls
    pending_audio: List[bytes] = []
    pending_ms: float = 0.0
    TRANSCRIBE_EVERY_MS: float = 3000.0

state = _State()


# ---------------------------------------------------------------------------
# Provider factories
# ---------------------------------------------------------------------------

def _build_llm(config: AppConfig) -> LLMProvider:
    match config.llm_provider:
        case LLMProviderType.OLLAMA:
            from llm.ollama import OllamaLLM
            return OllamaLLM(config.ollama_base_url, config.ollama_model)
        case LLMProviderType.OPENAI:
            from llm.openai_llm import OpenAILLM
            return OpenAILLM(config.openai_api_key, config.openai_model)
        case LLMProviderType.ANTHROPIC:
            from llm.anthropic_llm import AnthropicLLM
            return AnthropicLLM(config.anthropic_api_key, config.anthropic_model)
        case LLMProviderType.GEMINI:
            from llm.gemini_llm import GeminiLLM
            return GeminiLLM(config.gemini_api_key, config.gemini_model)
        case _:
            from llm.ollama import OllamaLLM
            return OllamaLLM()


def _build_stt(config: AppConfig) -> STTProvider:
    match config.stt_provider:
        case STTProviderType.LOCAL_WHISPER:
            from stt.whisper_local import LocalWhisperSTT
            return LocalWhisperSTT(config.whisper_model_size)
        case STTProviderType.OPENAI_API:
            from stt.whisper_api import WhisperAPISTT
            return WhisperAPISTT(config.openai_api_key)
        case _:
            from stt.whisper_local import LocalWhisperSTT
            return LocalWhisperSTT()


# ---------------------------------------------------------------------------
# WebSocket broadcast
# ---------------------------------------------------------------------------

async def _broadcast(message: dict) -> None:
    if not state.ws_clients:
        return
    data = json.dumps(message)
    dead: Set[WebSocket] = set()
    for ws in state.ws_clients:
        try:
            await ws.send_text(data)
        except Exception:
            dead.add(ws)
    state.ws_clients -= dead


# ---------------------------------------------------------------------------
# Audio pipeline
# ---------------------------------------------------------------------------

async def _on_audio_chunk(pcm_bytes: bytes, source: str, sample_rate: int) -> None:
    """Called from AudioCaptureManager for every audio chunk."""
    duration_ms = len(pcm_bytes) / 2 / sample_rate * 1000  # int16 = 2 bytes/sample
    state.pending_audio.append(pcm_bytes)
    state.pending_ms += duration_ms

    if state.pending_ms < state.TRANSCRIBE_EVERY_MS:
        return

    combined = b"".join(state.pending_audio)
    state.pending_audio.clear()
    state.pending_ms = 0.0

    if state.stt is None:
        return

    try:
        text = await state.stt.transcribe(combined, sample_rate)
    except Exception as exc:
        await _broadcast({"type": "error", "message": f"STT error: {exc}"})
        return

    if not text.strip():
        return

    state.buffer.add_segment(text, source)
    await _broadcast({
        "type": "transcript",
        "text": text,
        "source": source,
        "timestamp": time.time(),
    })


async def _on_answer(question: str, answer: str) -> None:
    await _broadcast({
        "type": "answer",
        "question": question,
        "answer": answer,
        "timestamp": time.time(),
    })


# ---------------------------------------------------------------------------
# Provider hot-reload
# ---------------------------------------------------------------------------

async def _reload_providers(config: AppConfig) -> None:
    """Tear down and rebuild STT/LLM providers from the new config."""
    import logging
    log = logging.getLogger("mk-qna")

    if state.stt:
        await state.stt.shutdown()
    state.stt = _build_stt(config)
    try:
        await state.stt.initialize()
    except Exception as e:
        log.warning(f"STT init failed: {e}")
        state.stt = None

    if state.llm:
        await state.llm.shutdown()
    state.llm = _build_llm(config)
    try:
        await state.llm.initialize()
    except Exception as e:
        log.warning(f"LLM init failed: {e}")
        state.llm = None

    # Rebuild detector with new LLM
    if state.detector:
        await state.detector.stop()
    state.detector = QuestionDetector(state.llm, state.buffer, config, _on_answer)

    if state.is_capturing and config.app_mode == AppMode.AUTO:
        await state.detector.start()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging
    log = logging.getLogger("mk-qna")
    state.config = load_config()
    state.buffer = TranscriptBuffer(state.config.transcript_buffer_minutes * 60)
    state.stt = _build_stt(state.config)
    state.llm = _build_llm(state.config)
    try:
        await state.stt.initialize()
    except Exception as e:
        log.warning(f"STT init failed (provider will be unavailable): {e}")
        state.stt = None
    try:
        await state.llm.initialize()
    except Exception as e:
        log.warning(f"LLM init failed (provider will be unavailable): {e}")
        state.llm = None
    state.detector = QuestionDetector(state.llm, state.buffer, state.config, _on_answer)
    yield
    # Shutdown
    if state.capture:
        await state.capture.stop()
    if state.detector:
        await state.detector.stop()
    if state.stt:
        await state.stt.shutdown()
    if state.llm:
        await state.llm.shutdown()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="MK-Live Q&A Assistant", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.get("/api/status")
async def get_status():
    return {
        "capturing": state.is_capturing,
        "mode": state.config.app_mode,
        "stt": state.config.stt_provider,
        "llm": state.config.llm_provider,
    }


@app.get("/api/config")
async def get_config():
    return state.config.model_dump()


@app.post("/api/config")
async def post_config(new_config: AppConfig):
    save_config(new_config)
    state.config = new_config
    state.buffer = TranscriptBuffer(new_config.transcript_buffer_minutes * 60)
    await _reload_providers(new_config)
    await _broadcast({"type": "status", "capturing": state.is_capturing, "mode": new_config.app_mode})
    return new_config.model_dump()


@app.get("/api/devices")
async def get_devices():
    from audio.capture import AudioCaptureManager
    loop = asyncio.get_event_loop()
    temp_manager = AudioCaptureManager(state.config, _on_audio_chunk, loop)
    return temp_manager.list_input_devices()


@app.get("/api/ollama/models")
async def get_ollama_models():
    try:
        from llm.ollama import OllamaLLM
        ollama = OllamaLLM(state.config.ollama_base_url)
        await ollama.initialize()
        models = await ollama.list_models()
        await ollama.shutdown()
        return models
    except Exception:
        return []


@app.post("/api/start")
async def start_capture():
    if state.is_capturing:
        return {"status": "already running"}

    from audio.capture import AudioCaptureManager
    loop = asyncio.get_event_loop()
    state.capture = AudioCaptureManager(state.config, _on_audio_chunk, loop)
    await state.capture.start()
    state.is_capturing = True

    if state.config.app_mode == AppMode.AUTO and state.detector:
        await state.detector.start()

    await _broadcast({"type": "status", "capturing": True, "mode": state.config.app_mode})
    return {"status": "started"}


@app.post("/api/stop")
async def stop_capture():
    if not state.is_capturing:
        return {"status": "not running"}

    if state.capture:
        await state.capture.stop()
        state.capture = None

    if state.detector:
        await state.detector.stop()

    state.is_capturing = False
    state.pending_audio.clear()
    state.pending_ms = 0.0

    await _broadcast({"type": "status", "capturing": False, "mode": state.config.app_mode})
    return {"status": "stopped"}


@app.post("/api/trigger")
async def manual_trigger():
    if not state.detector:
        return JSONResponse({"error": "Not initialized"}, status_code=503)

    question, answer = await state.detector.manual_trigger(state.config.manual_lookback_seconds)
    await _broadcast({
        "type": "answer",
        "question": question,
        "answer": answer,
        "timestamp": time.time(),
    })
    return {"question": question, "answer": answer}


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    state.ws_clients.add(ws)
    # Send current status immediately on connect
    await ws.send_text(json.dumps({
        "type": "status",
        "capturing": state.is_capturing,
        "mode": state.config.app_mode,
    }))
    try:
        while True:
            await ws.receive_text()  # keep connection alive; clients may send pings
    except WebSocketDisconnect:
        pass
    finally:
        state.ws_clients.discard(ws)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    uvicorn.run("main:app", host=args.host, port=args.port, log_level="info")
