"""
Iris Edge Neural TTS Module
============================
Synthesizes studio-quality, human-like neural voices without requiring
any API keys, user accounts, or cloud subscriptions:
- Indian English: 'en-IN-NeerjaNeural'
- Hindi: 'hi-IN-SwaraNeural'
- US English: 'en-US-JennyNeural'

Streams audio directly in RAM via pygame.mixer (zero disk clutter).
"""

from __future__ import annotations

import io
import asyncio
import logging
import threading
from typing import Dict, Optional

logger = logging.getLogger("IrisEdgeTTS")

VOICE_MAP = {
    "hi": "hi-IN-SwaraNeural",
    "en": "en-IN-NeerjaNeural",
    "en-us": "en-US-JennyNeural",
}

# In-memory audio byte cache for high-frequency short phrases
_edge_audio_cache: Dict[str, bytes] = {}
_cache_lock = threading.Lock()
MAX_CACHE_ITEMS = 64


async def _synthesize_edge_bytes(text: str, voice: str) -> Optional[bytes]:
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        fp = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fp.write(chunk["data"])
        fp.seek(0)
        return fp.getvalue()
    except Exception as exc:
        logger.debug("edge-tts stream error: %s", exc)
        return None


def synthesize_edge_audio(text: str, lang: str = "en") -> Optional[bytes]:
    clean_text = text.strip()
    if not clean_text:
        return None

    voice = VOICE_MAP.get(lang, "en-IN-NeerjaNeural")
    cache_key = f"{voice}:{clean_text}"

    with _cache_lock:
        if cache_key in _edge_audio_cache:
            return _edge_audio_cache[cache_key]

    try:
        # Run asyncio event loop safely in synchronous wrapper
        audio_bytes = asyncio.run(_synthesize_edge_bytes(clean_text, voice))
        if audio_bytes:
            with _cache_lock:
                if len(_edge_audio_cache) >= MAX_CACHE_ITEMS:
                    _edge_audio_cache.pop(next(iter(_edge_audio_cache)))
                _edge_audio_cache[cache_key] = audio_bytes
            return audio_bytes
    except Exception as exc:
        logger.debug("Failed edge-tts synthesis: %s", exc)

    return None


def speak_with_edge_tts(text: str, lang: str = "en") -> bool:
    """
    Synthesizes speech using Edge Neural TTS and plays directly from RAM.
    Returns True if audio successfully played, False otherwise.
    """
    audio_bytes = synthesize_edge_audio(text, lang=lang)
    if not audio_bytes:
        return False

    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=24000, size=-16, channels=2, buffer=512)

        sound_file = io.BytesIO(audio_bytes)
        pygame.mixer.music.load(sound_file)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(30)

        return True
    except Exception as exc:
        logger.debug("Edge-TTS pygame playback error: %s", exc)
        return False
