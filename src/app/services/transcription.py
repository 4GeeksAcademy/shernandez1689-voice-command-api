from fastapi import HTTPException, status
from groq import GroqError

from src.app.core.config import get_settings
from src.app.services.groq_client import get_groq_client


_WEBM_HEADER = b"\x1a\x45\xdf\xa3"


def strip_leading_garbage(audio: bytes) -> bytes:
    """Drop bytes before the WebM header.

    The frontend can leave chunks from the previous recording at the start of the
    next blob, which makes Whisper reject the file as invalid media.
    """
    start = audio.find(_WEBM_HEADER)
    return audio[start:] if start > 0 else audio


def transcribe_audio(filename: str, audio: bytes, language: str | None = None) -> str:
    settings = get_settings()
    try:
        result = get_groq_client().audio.transcriptions.create(
            file=(filename, audio),
            model=settings.groq_transcription_model,
            language=language,
            temperature=0,
        )
    except GroqError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Groq transcription failed: {exc}",
        ) from exc

    text = (result.text or "").strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No speech was detected in the audio.",
        )
    return text
