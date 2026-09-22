import json
import platform
from enum import Enum
from pathlib import Path
from typing import Optional

from platformdirs import user_data_dir
from pydantic import BaseModel


class STTProviderType(str, Enum):
    LOCAL_WHISPER = "local_whisper"
    OPENAI_API = "openai_api"


class LLMProviderType(str, Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class AudioSourceType(str, Enum):
    MIC = "mic"
    LOOPBACK = "loopback"
    BOTH = "both"


class AppMode(str, Enum):
    AUTO = "auto"
    MANUAL = "manual"


class AppConfig(BaseModel):
    # Audio
    audio_source: AudioSourceType = AudioSourceType.MIC
    mic_device_index: Optional[int] = None
    loopback_device_index: Optional[int] = None

    # STT
    stt_provider: STTProviderType = STTProviderType.LOCAL_WHISPER
    whisper_model_size: str = "base"

    # LLM
    llm_provider: LLMProviderType = LLMProviderType.OLLAMA
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-haiku-20240307"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    # Mode
    app_mode: AppMode = AppMode.MANUAL
    manual_lookback_seconds: int = 45
    auto_check_interval_seconds: int = 5

    # Transcript
    transcript_buffer_minutes: int = 5


def get_config_path() -> Path:
    data_dir = Path(user_data_dir("MKLiveQnA", "MK"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "config.json"


def load_config() -> AppConfig:
    path = get_config_path()
    if path.exists():
        try:
            return AppConfig.model_validate_json(path.read_text())
        except Exception:
            pass
    config = AppConfig()
    save_config(config)
    return config


def save_config(config: AppConfig) -> None:
    path = get_config_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(config.model_dump_json(indent=2))
    tmp.replace(path)
