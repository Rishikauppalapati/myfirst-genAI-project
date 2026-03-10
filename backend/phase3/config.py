from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class GroqConfig:
    api_key_env: str = "GROQ_API_KEY"
    model: str = "llama3-8b-8192"
    temperature: float = 0.2
    max_output_tokens: int = 1024


def _load_env_files() -> None:
    """
    Load environment variables from common .env locations so that
    GROQ_API_KEY can be kept in a file instead of global OS env.
    """
    # Generic .env in project root (if you choose to create it)
    load_dotenv(override=False)

    # Also support ./env/.env next to the example file
    base_dir = Path(__file__).resolve().parent.parent
    env_path = base_dir / "env" / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


def get_groq_api_key(config: GroqConfig | None = None) -> str:
    """Fetch the Groq API key from the environment (after loading .env files)."""
    _load_env_files()
    cfg = config or GroqConfig()
    api_key = os.getenv(cfg.api_key_env)
    if not api_key:
        raise RuntimeError(
            f"Groq API key not found. Please set environment variable '{cfg.api_key_env}' "
            "or add it to a .env file."
        )
    return api_key

