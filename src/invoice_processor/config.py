"""Application configuration loaded from environment variables."""

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Small, explicit collection of settings used by the application."""

    openai_api_key: str
    openai_model: str


def load_settings() -> Settings:
    """Load local settings, allowing a .env file during development."""

    load_dotenv()
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
    )
