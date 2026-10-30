from functools import lru_cache

from groq import Groq

from src.app.core.config import get_settings


@lru_cache
def get_groq_client() -> Groq:
    settings = get_settings()
    return Groq(api_key=settings.groq_api_key, timeout=settings.request_timeout_seconds)
