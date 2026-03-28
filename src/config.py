import os
from pydantic import BaseModel, Field
from typing import Any, Optional
from langchain_core.runnables import RunnableConfig
from langchain_ollama import ChatOllama
from langchain_core.language_models import BaseChatModel
from langchain.chat_models import init_chat_model

from dotenv import load_dotenv

load_dotenv()


class Configuration(BaseModel):
    """Configuration for the agent, Whisper STT, and Piper TTS."""

    # ── LLM ───────────────────────────────────────────────────────
    smart_llm: str = Field(
        default="ollama:qwen2.5:7b-instruct",
        description="Smart/capable model for reasoning tasks",
    )
    fast_llm: str = Field(
        default="ollama:qwen2.5:3b-instruct",
        description="Fast model for lightweight decisions",
    )
    ollama_endpoints: list[str] = Field(
        default=["http://localhost:11434"],
        description="List of Ollama base URLs for load distribution",
    )
    temperature: float = Field(
        default=0.3,
        description="LLM sampling temperature",
    )
    max_workers: Optional[int] = Field(
        default=None,
        description="Cap parallelism. None = use get_optimal_workers()",
    )
    max_rewrite_attempts: int = Field(
        default=3,
        description="How many times to retry a rewrite if quality check fails",
    )

    # ── Speech-to-Text (Whisper) ──────────────────────────────────
    whisper_model: str = Field(
        default="base",
        description="faster-whisper model size: tiny | base | small | medium | large",
    )
    whisper_device: str = Field(
        default="cpu",
        description="Inference device for Whisper: cpu | cuda",
    )
    whisper_compute_type: str = Field(
        default="int8",
        description="Compute type for faster-whisper: int8 | float16 | float32",
    )
    whisper_language: Optional[str] = Field(
        default=None,
        description="Force a language code (e.g. 'en'). None = auto-detect.",
    )

    # ── Text-to-Speech (Piper via Wyoming) ───────────────────────
    piper_host: str = Field(
        default="localhost",
        description="Hostname of the Piper Wyoming TTS server",
    )
    piper_port: int = Field(
        default=10200,
        description="TCP port of the Piper Wyoming TTS server",
    )
    piper_voice: str = Field(
        default="en_US-lessac-medium",
        description="Piper voice model name (must be downloaded in the container)",
    )

    # ── Helpers ───────────────────────────────────────────────────
    def _is_ollama(self, model: str) -> bool:
        return model.startswith("ollama:")

    def get_smart_llm(self, endpoint_index: int = 0) -> BaseChatModel:
        if self._is_ollama(self.smart_llm):
            return ChatOllama(
                model=self.smart_llm.split(":", 1)[1],
                temperature=self.temperature,
                base_url=self.ollama_endpoints[endpoint_index],
            )
        return init_chat_model(self.smart_llm, temperature=self.temperature)

    def get_fast_llm(self) -> BaseChatModel:
        if self._is_ollama(self.fast_llm):
            return ChatOllama(
                model=self.fast_llm.split(":", 1)[1],
                temperature=self.temperature,
                base_url=self.ollama_endpoints[0],
            )
        return init_chat_model(self.fast_llm, temperature=self.temperature)

    def is_local(self, model: str) -> bool:
        return not any(
            model.startswith(prefix)
            for prefix in ("claude", "gpt", "openai", "anthropic")
        )

    def get_optimal_workers(self) -> int:
        if self._is_ollama(self.smart_llm):
            return len(self.ollama_endpoints)
        elif self.max_workers is not None:
            return self.max_workers
        return -1

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "Configuration":
        """Load configuration from environment variables or a RunnableConfig dict."""
        configurable = config.get("configurable", {}) if config else {}
        values: dict[str, Any] = {}

        for f in cls.model_fields:
            env_val = os.environ.get(f.upper())
            cfg_val = configurable.get(f)
            raw = env_val if env_val is not None else cfg_val

            # ollama_endpoints arrives as a comma-separated string from env vars
            if f == "ollama_endpoints" and isinstance(raw, str):
                raw = [u.strip() for u in raw.split(",") if u.strip()]

            if raw is not None:
                values[f] = raw

        return cls(**values)