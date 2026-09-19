"""
Iris Amazon Bedrock Intelligence Layer
=======================================
Integrates Amazon Bedrock foundation models (Claude 3.5 Haiku, Amazon Nova Micro,
or Titan) for intent reasoning, complex task planning, and accessibility conversation.
Uses the high-performance Converse API with automatic fallback.
"""

from __future__ import annotations

import os
import time
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("IrisBedrockClient")

REGION_NAME = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
DEFAULT_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-haiku-20241022-v1:0")

_bedrock_client = None


def get_bedrock_client():
    """Returns a cached boto3 bedrock-runtime client if real credentials exist."""
    global _bedrock_client
    if _bedrock_client is None:
        key = os.getenv("AWS_ACCESS_KEY_ID", "")
        if not key or key.startswith("your_") or key == "test":
            return None
        try:
            import boto3
            _bedrock_client = boto3.client("bedrock-runtime", region_name=REGION_NAME)
        except Exception as exc:
            logger.debug("Could not initialize Amazon Bedrock client: %s", exc)
            return None
    return _bedrock_client


def query_bedrock(
    user_prompt: str,
    system_prompt: str = "You are Iris, a concise accessibility voice assistant for Windows. Answer in 1 short spoken sentence.",
    model_id: Optional[str] = None
) -> Tuple[Optional[str], float]:
    """
    Queries Amazon Bedrock via Converse API.
    Returns (response_text, latency_ms). Returns (None, 0.0) if unavailable.
    """
    client = get_bedrock_client()
    if not client:
        return None, 0.0

    target_model = model_id or DEFAULT_MODEL_ID
    start_time = time.time()

    try:
        messages = [
            {
                "role": "user",
                "content": [{"text": user_prompt}]
            }
        ]
        system = [{"text": system_prompt}] if system_prompt else []

        response = client.converse(
            modelId=target_model,
            messages=messages,
            system=system,
            inferenceConfig={
                "maxTokens": 150,
                "temperature": 0.2,
            }
        )

        latency_ms = (time.time() - start_time) * 1000.0
        output_msg = response.get("output", {}).get("message", {})
        contents = output_msg.get("content", [])
        if contents and "text" in contents[0]:
            answer = contents[0]["text"].strip()
            return answer, latency_ms

    except Exception as exc:
        logger.debug("Amazon Bedrock invocation failed (%s): %s", target_model, exc)
        return None, (time.time() - start_time) * 1000.0

    return None, 0.0
