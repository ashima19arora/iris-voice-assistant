"""
Iris Amazon Polly Neural TTS Narration Module
==============================================
Synthesizes broadcast-quality, natural human speech using Amazon Polly Neural voices:
- Hindi & Indian English: 'Aditi' / 'Kajal'
- Standard English: 'Joanna' / 'Matthew'

Plays audio streams directly from RAM via pygame.mixer (zero temporary disk files)
and maintains an in-memory cache for repeated accessibility phrases.
"""

from __future__ import annotations

import io
import os
import sys
import logging
import threading
from typing import Dict, Optional
from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)

logger = logging.getLogger("IrisPollyTTS")

def get_region() -> str:
    return os.getenv("AWS_DEFAULT_REGION", "eu-north-1")

def get_voice_en() -> str:
    return os.getenv("POLLY_VOICE_EN", "Joanna")

def get_voice_hi() -> str:
    return os.getenv("POLLY_VOICE_HI", "Aditi")

_polly_client = None
_client_lock = threading.Lock()

# In-memory audio byte cache for high-frequency phrases
_audio_cache: Dict[str, bytes] = {}
_cache_lock = threading.Lock()
MAX_CACHE_ITEMS = 64


def get_polly_client():
    """Returns a cached boto3 Polly client if real credentials exist."""
    global _polly_client
    with _client_lock:
        if _polly_client is None:
            key = os.getenv("AWS_ACCESS_KEY_ID", "")
            if not key or key.startswith("your_") or key == "test":
                return None
            try:
                import boto3
                _polly_client = boto3.client("polly", region_name=get_region())
            except Exception as exc:
                logger.debug("Could not initialize Amazon Polly client: %s", exc)
                return None
    return _polly_client


def synthesize_polly_audio(text: str, lang: str = "en") -> Optional[bytes]:
    """
    Synthesizes speech using Amazon Polly and returns MP3 audio bytes.
    """
    clean_text = text.strip()
    if not clean_text:
        return None

    cache_key = f"{lang}:{clean_text}"
    with _cache_lock:
        if cache_key in _audio_cache:
            return _audio_cache[cache_key]

    client = get_polly_client()
    if not client:
        return None

    voice_id = get_voice_hi() if lang == "hi" else get_voice_en()
    try:
        # Aditi only supports standard engine; Joanna supports neural
        preferred_engine = "standard" if voice_id == "Aditi" else "neural"
        try:
            response = client.synthesize_speech(
                Text=clean_text,
                OutputFormat="mp3",
                VoiceId=voice_id,
                Engine=preferred_engine
            )
        except Exception:
            # Fallback to standard engine if neural is unavailable for voice
            response = client.synthesize_speech(
                Text=clean_text,
                OutputFormat="mp3",
                VoiceId=voice_id,
                Engine="standard"
            )

        if "AudioStream" in response:
            audio_bytes = response["AudioStream"].read()
            with _cache_lock:
                if len(_audio_cache) >= MAX_CACHE_ITEMS:
                    _audio_cache.pop(next(iter(_audio_cache)))
                _audio_cache[cache_key] = audio_bytes
            return audio_bytes

    except Exception as exc:
        logger.debug("Amazon Polly synthesis failed: %s", exc)
        return None

    return None


def speak_with_polly(text: str, lang: str = "en") -> bool:
    """
    Synthesizes and plays audio through pygame.mixer directly from RAM.
    Returns True on success, False on failure.
    """
    audio_bytes = synthesize_polly_audio(text, lang=lang)
    if not audio_bytes:
        return False

    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)

        sound_file = io.BytesIO(audio_bytes)
        pygame.mixer.music.load(sound_file)
        pygame.mixer.music.play()

        # Wait until playback completes
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(30)

        return True
    except Exception as exc:
        logger.debug("Polly audio playback error: %s", exc)
        return False
