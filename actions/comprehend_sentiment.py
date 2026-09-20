"""
Iris Amazon Comprehend — Sentiment-Aware Voice Response Adaptation
===================================================================
WHAT THIS FILE DOES (Simple English):
  Analyzes the emotional sentiment of user voice commands using Amazon Comprehend.
  When a user sounds frustrated, confused, or negative, Iris adapts its tone to be
  more empathetic and supportive. This creates a more human-like, emotionally
  intelligent assistant experience.

GREAT TECH & PACKAGES USED IN THIS FILE:
  - Amazon Comprehend:
      * What it does: NLP service that detects sentiment (POSITIVE, NEGATIVE, NEUTRAL, MIXED)
        and dominant language from text.
      * Why we use it: Enables Iris to respond empathetically when users are frustrated,
        making the assistant feel emotionally aware and human-like.
"""

from __future__ import annotations

import os
import logging
import threading
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("IrisComprehend")

REGION_NAME = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

_comprehend_client = None
_client_lock = threading.Lock()


@dataclass
class SentimentResult:
    """Result of sentiment analysis."""
    sentiment: str           # POSITIVE, NEGATIVE, NEUTRAL, MIXED
    positive_score: float
    negative_score: float
    neutral_score: float
    mixed_score: float
    is_frustrated: bool      # convenience flag for response adaptation


def get_comprehend_client():
    """Returns a cached boto3 Comprehend client if real AWS credentials exist."""
    global _comprehend_client
    with _client_lock:
        if _comprehend_client is None:
            key = os.getenv("AWS_ACCESS_KEY_ID", "")
            if not key or key.startswith("your_") or key == "test":
                return None
            try:
                import boto3
                _comprehend_client = boto3.client("comprehend", region_name=REGION_NAME)
            except Exception as exc:
                logger.debug("Could not initialize Amazon Comprehend client: %s", exc)
                return None
    return _comprehend_client


def analyze_sentiment(text: str) -> Optional[SentimentResult]:
    """
    Analyzes the sentiment of user input using Amazon Comprehend.
    Returns None if Comprehend is unavailable, or a SentimentResult with scores.
    """
    clean = text.strip()
    if not clean or len(clean) < 3:
        return None

    client = get_comprehend_client()
    if not client:
        return _fallback_keyword_sentiment(clean)

    try:
        response = client.detect_sentiment(
            Text=clean[:5000],  # Comprehend limit
            LanguageCode="en",
        )

        sentiment = response.get("Sentiment", "NEUTRAL")
        scores = response.get("SentimentScore", {})

        result = SentimentResult(
            sentiment=sentiment,
            positive_score=scores.get("Positive", 0.0),
            negative_score=scores.get("Negative", 0.0),
            neutral_score=scores.get("Neutral", 0.0),
            mixed_score=scores.get("Mixed", 0.0),
            is_frustrated=(sentiment == "NEGATIVE" and scores.get("Negative", 0) > 0.55),
        )

        logger.info(
            "Sentiment: %s (pos=%.2f neg=%.2f neu=%.2f mix=%.2f)",
            result.sentiment, result.positive_score, result.negative_score,
            result.neutral_score, result.mixed_score,
        )
        return result

    except Exception as exc:
        logger.debug("Amazon Comprehend sentiment failed: %s", exc)
        return _fallback_keyword_sentiment(clean)


def _fallback_keyword_sentiment(text: str) -> SentimentResult:
    """Simple keyword-based sentiment fallback when Comprehend is unavailable."""
    lower = text.lower()
    frustrated_keywords = {
        "frustrated", "frustrating", "annoying", "annoyed", "angry", "stupid",
        "broken", "not working", "doesn't work", "fix this", "come on",
        "useless", "terrible", "worst", "hate", "ugh", "damn", "why won't",
    }
    positive_keywords = {
        "thank", "thanks", "great", "good", "amazing", "awesome", "perfect",
        "love", "excellent", "wonderful", "nice", "cool", "brilliant",
    }

    neg_count = sum(1 for kw in frustrated_keywords if kw in lower)
    pos_count = sum(1 for kw in positive_keywords if kw in lower)

    if neg_count > pos_count:
        return SentimentResult(
            sentiment="NEGATIVE",
            positive_score=0.1, negative_score=0.7,
            neutral_score=0.1, mixed_score=0.1,
            is_frustrated=True,
        )
    elif pos_count > neg_count:
        return SentimentResult(
            sentiment="POSITIVE",
            positive_score=0.7, negative_score=0.1,
            neutral_score=0.1, mixed_score=0.1,
            is_frustrated=False,
        )
    return SentimentResult(
        sentiment="NEUTRAL",
        positive_score=0.1, negative_score=0.1,
        neutral_score=0.7, mixed_score=0.1,
        is_frustrated=False,
    )


def get_empathetic_prefix(sentiment: Optional[SentimentResult], lang: str = "en") -> str:
    """
    Returns an empathetic prefix for Iris's response based on detected sentiment.
    This makes Iris feel emotionally aware and human-like.
    """
    if sentiment is None:
        return ""

    if sentiment.is_frustrated:
        if lang == "hi":
            return "मैं समझ रहा हूँ, मैं तुरंत मदद करता हूँ। "
        return "I understand, let me help you right away. "

    if sentiment.sentiment == "POSITIVE" and sentiment.positive_score > 0.7:
        if lang == "hi":
            return "बढ़िया! "
        return "Great! "

    return ""
