"""Spoken confirmation for SENSITIVE tools. Default listen timeout is CONFIRMATION_TIMEOUT_SEC (8s)."""
from __future__ import annotations

import logging
from typing import Callable, Optional

from .config import CONFIRMATION_TIMEOUT_SEC
from .feedback import speak

logger = logging.getLogger("iris")

YES_PHRASES = ("yes", "yeah", "yep", "sure", "go ahead", "do it", "ok", "okay", "haan", "ha")


def parse_confirmation(heard: str) -> bool:
    """Accept only explicit yes-family phrases; everything else is no."""
    text = " ".join((heard or "").lower().strip().split())
    if not text:
        return False
    for phrase in YES_PHRASES:
        if text == phrase or text.startswith(phrase + " ") or f" {phrase} " in f" {text} ":
            return True
    return False


def request_confirmation(
    prompt: str,
    *,
    lang: str = "en",
    listen_fn: Optional[Callable[..., Optional[str]]] = None,
    timeout: float = CONFIRMATION_TIMEOUT_SEC,
) -> bool:
    logger.info("confirmation prompt: %s", prompt)
    speak(prompt, lang=lang)
    if listen_fn is None:
        heard = _listen_once(timeout)
    else:
        heard = listen_fn(timeout=timeout)
    logger.info("confirmation response: %r", heard)
    if heard is None:
        logger.warning("confirmation timeout after %.1fs — cancelled", timeout)
        speak("Cancelled. I did not hear a yes." if lang != "hi" else "रद्द किया गया।", lang=lang)
        return False
    if parse_confirmation(heard):
        return True
    speak("Cancelled." if lang != "hi" else "रद्द किया गया।", lang=lang)
    return False


def _listen_once(timeout: float) -> Optional[str]:
    """One-shot microphone listen; returns None on timeout/error (never raises)."""
    try:
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=min(timeout, 4.0))
        return recognizer.recognize_google(audio)
    except Exception:
        return None
