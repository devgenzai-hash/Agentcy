"""Central configuration loaded from .env"""
from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _b(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "y"}


@dataclass(frozen=True)
class Settings:
    ai_provider: str = os.getenv("AI_PROVIDER", "nvidia-nim")
    ai_api_key: str = os.getenv("AI_API_KEY", "")
    ai_model: str = os.getenv("AI_MODEL", "meta/llama-3.1-8b-instruct")
    ai_base_url: str = os.getenv("AI_BASE_URL", "")

    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "nvidia-nim")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "nvidia/nv-embedqa-e5-v5")
    embedding_dimensions: int = int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))
    embedding_api_key: str = os.getenv("EMBEDDING_API_KEY", "") or os.getenv("AI_API_KEY", "")
    embedding_base_url: str = os.getenv("EMBEDDING_BASE_URL", "")

    sqlite_path: str = os.getenv("SQLITE_PATH", "data/agentswarm.db")
    chroma_path: str = os.getenv("CHROMA_PATH", "data/chroma")

    max_agents: int = int(os.getenv("MAX_AGENTS", "32"))
    human_in_the_loop: bool = _b("HUMAN_IN_THE_LOOP", True)

    scrape_concurrency: int = int(os.getenv("SCRAPE_CONCURRENCY", "8"))
    scrape_timeout: int = int(os.getenv("SCRAPE_TIMEOUT", "20"))
    user_agent: str = os.getenv("USER_AGENT", "AgentSwarm/0.1")


settings = Settings()

# Provider default base URLs (OpenAI-compatible endpoints)
PROVIDER_BASE_URLS = {
    "nvidia-nim": "https://integrate.api.nvidia.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://localhost:11434/v1",
    "llama-cpp": "http://localhost:8080/v1",
    "openai": "https://api.openai.com/v1",
}


def resolve_base_url(provider: str, override: str = "") -> str:
    return override or PROVIDER_BASE_URLS.get(provider, PROVIDER_BASE_URLS["openai"])
