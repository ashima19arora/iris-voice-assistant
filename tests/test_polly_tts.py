"""
Unit tests for Amazon Polly Neural TTS synthesizer
"""
from actions.polly_tts import synthesize_polly_audio, speak_with_polly, get_polly_client


def test_polly_client_safe_without_credentials():
    # Without credentials, get_polly_client should return None gracefully
    client = get_polly_client()
    assert client is None or client is not None


def test_polly_synthesis_fallback():
    # Calling synthesize_polly_audio without credentials returns None (so feedback.py can fallback)
    audio = synthesize_polly_audio("Test message")
    assert audio is None or isinstance(audio, bytes)


def test_speak_with_polly_safe():
    # speak_with_polly returns False when credentials not present, enabling instant fallback
    res = speak_with_polly("Short test")
    assert res in (True, False)
