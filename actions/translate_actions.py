"""
Iris Amazon Translate — Real-Time Multilingual Voice Translation
================================================================
WHAT THIS FILE DOES (Simple English):
  Enables instant voice-powered translation across 75+ languages using Amazon Translate.
  When a user says "translate hello how are you to Japanese", Iris translates the text
  and speaks the result back using Amazon Polly TTS — creating a real-time voice translator.

GREAT TECH & PACKAGES USED IN THIS FILE:
  - Amazon Translate:
      * What it does: Neural machine translation service supporting 75+ languages.
      * Why we use it: Provides near-human-quality translations in real-time with
        automatic language detection for the source language.
  - Amazon Polly (via feedback.speak):
      * What it does: Speaks the translated text aloud.
      * Why we use it: Completes the voice-to-voice translation loop hands-free.
"""

from __future__ import annotations

import os
import logging
import threading
from typing import Dict, Optional, Tuple

from .feedback import speak, notify

logger = logging.getLogger("IrisTranslate")

REGION_NAME = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

_translate_client = None
_client_lock = threading.Lock()

# Comprehensive language code mapping for voice commands
LANGUAGE_MAP: Dict[str, str] = {
    "arabic": "ar", "bengali": "bn", "chinese": "zh", "simplified chinese": "zh",
    "traditional chinese": "zh-TW", "czech": "cs", "danish": "da", "dutch": "nl",
    "english": "en", "finnish": "fi", "french": "fr", "german": "de", "greek": "el",
    "gujarati": "gu", "hebrew": "he", "hindi": "hi", "hungarian": "hu",
    "indonesian": "id", "italian": "it", "japanese": "ja", "kannada": "kn",
    "korean": "ko", "malay": "ms", "malayalam": "ml", "marathi": "mr",
    "norwegian": "no", "persian": "fa", "polish": "pl", "portuguese": "pt",
    "punjabi": "pa", "romanian": "ro", "russian": "ru", "serbian": "sr",
    "sinhala": "si", "slovak": "sk", "spanish": "es", "swedish": "sv",
    "tamil": "ta", "telugu": "te", "thai": "th", "turkish": "tr",
    "ukrainian": "uk", "urdu": "ur", "vietnamese": "vi", "welsh": "cy",
}


def get_translate_client():
    """Returns a cached boto3 Translate client if real AWS credentials exist."""
    global _translate_client
    with _client_lock:
        if _translate_client is None:
            key = os.getenv("AWS_ACCESS_KEY_ID", "")
            if not key or key.startswith("your_") or key == "test":
                return None
            try:
                import boto3
                _translate_client = boto3.client("translate", region_name=REGION_NAME)
            except Exception as exc:
                logger.debug("Could not initialize Amazon Translate client: %s", exc)
                return None
    return _translate_client


def resolve_language_code(lang_name: str) -> str:
    """Resolves a spoken language name to an AWS Translate language code."""
    cleaned = lang_name.strip().lower()
    if cleaned in LANGUAGE_MAP:
        return LANGUAGE_MAP[cleaned]
    # Partial match (e.g., "span" → "spanish")
    for name, code in LANGUAGE_MAP.items():
        if name.startswith(cleaned) or cleaned.startswith(name):
            return code
    # If it looks like a 2-letter code already, return as-is
    if len(cleaned) <= 5 and cleaned.isalpha():
        return cleaned
    return cleaned


def translate_text(
    text: str,
    target_language: str,
    source_language: str = "auto",
    lang: str = "en",
) -> Tuple[bool, str]:
    """
    Translates text using Amazon Translate.
    Returns (success, translated_text_or_error_message).
    """
    text = text.strip()
    if not text:
        return False, "No text to translate."

    target_code = resolve_language_code(target_language)
    source_code = resolve_language_code(source_language) if source_language != "auto" else "auto"

    client = get_translate_client()
    if not client:
        # Graceful fallback: use the LLM for translation
        return _fallback_llm_translate(text, target_language, lang)

    try:
        params = {
            "Text": text,
            "TargetLanguageCode": target_code,
        }
        if source_code != "auto":
            params["SourceLanguageCode"] = source_code
        else:
            params["SourceLanguageCode"] = "auto"

        response = client.translate_text(**params)
        translated = response.get("TranslatedText", "")
        source_detected = response.get("SourceLanguageCode", "?")

        if translated:
            logger.info(
                "Translated [%s→%s]: '%s' → '%s'",
                source_detected, target_code, text[:50], translated[:50],
            )
            return True, translated

    except Exception as exc:
        logger.warning("Amazon Translate failed: %s — using LLM fallback", exc)
        return _fallback_llm_translate(text, target_language, lang)

    return False, "Translation returned empty result."


def _fallback_llm_translate(text: str, target_lang: str, lang: str) -> Tuple[bool, str]:
    """Falls back to LLM-based translation when AWS Translate is unavailable."""
    try:
        from .llm_client import ask_openrouter
        prompt = f"Translate the following text to {target_lang}. Return ONLY the translation, nothing else:\n\n{text}"
        answer = ask_openrouter(prompt)
        if answer:
            return True, answer.strip()
    except Exception as exc:
        logger.debug("LLM translation fallback also failed: %s", exc)
    return False, "Translation is not available right now."


def translate_and_speak(
    text: str,
    target_language: str,
    source_language: str = "auto",
    lang: str = "en",
) -> bool:
    """
    Full voice translation flow: translate text and speak the result aloud.
    """
    notify(f"Translating to {target_language}...")
    speak(
        f"{target_language} में अनुवाद कर रहा हूँ" if lang == "hi"
        else f"Translating to {target_language}",
        lang=lang,
    )

    success, result = translate_text(text, target_language, source_language, lang)

    if success:
        notify(f"Translation ({target_language}): {result}")
        speak(result, lang=lang)
        return True
    else:
        notify(f"Translation failed: {result}", success=False)
        speak(
            "माफ़ करें, अनुवाद नहीं हो पाया" if lang == "hi"
            else "Sorry, I could not translate that.",
            lang=lang,
        )
        return False
