"""
Iris Amazon CloudWatch — Voice Command Observability & Analytics
=================================================================
WHAT THIS FILE DOES (Simple English):
  Publishes real-time metrics and structured logs for every voice command to Amazon
  CloudWatch. This creates a production-grade observability layer showing:
  - Command success/failure rates
  - Intent distribution (which commands are used most)
  - Latency percentiles (how fast Iris responds)
  - Error tracking and alerting

GREAT TECH & PACKAGES USED IN THIS FILE:
  - Amazon CloudWatch (Metrics):
      * What it does: Time-series metrics dashboard with automatic graphing.
      * Why we use it: Enables real-time monitoring of Iris performance and usage patterns.
  - Amazon CloudWatch (Logs):
      * What it does: Structured log aggregation with search and filter.
      * Why we use it: Every voice command is logged for audit, debugging, and analytics.
"""

from __future__ import annotations

import os
import time
import json
import logging
import threading
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger("IrisCloudWatch")

REGION_NAME = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
NAMESPACE = "IrisVoiceAssistant"
LOG_GROUP = "/iris/voice-commands"
LOG_STREAM_PREFIX = "iris-session"

_cw_client = None
_logs_client = None
_client_lock = threading.Lock()
_log_stream_name: Optional[str] = None
_log_sequence_token: Optional[str] = None


def _get_cw_client():
    """Returns a cached CloudWatch metrics client."""
    global _cw_client
    with _client_lock:
        if _cw_client is None:
            key = os.getenv("AWS_ACCESS_KEY_ID", "")
            if not key or key.startswith("your_") or key == "test":
                return None
            try:
                import boto3
                _cw_client = boto3.client("cloudwatch", region_name=REGION_NAME)
            except Exception as exc:
                logger.debug("Could not initialize CloudWatch client: %s", exc)
                return None
    return _cw_client


def _get_logs_client():
    """Returns a cached CloudWatch Logs client."""
    global _logs_client
    with _client_lock:
        if _logs_client is None:
            key = os.getenv("AWS_ACCESS_KEY_ID", "")
            if not key or key.startswith("your_") or key == "test":
                return None
            try:
                import boto3
                _logs_client = boto3.client("logs", region_name=REGION_NAME)
            except Exception as exc:
                logger.debug("Could not initialize CloudWatch Logs client: %s", exc)
                return None
    return _logs_client


def _ensure_log_stream():
    """Creates the log group and stream if they don't exist."""
    global _log_stream_name, _log_sequence_token

    if _log_stream_name:
        return _log_stream_name

    client = _get_logs_client()
    if not client:
        return None

    try:
        client.create_log_group(logGroupName=LOG_GROUP)
    except Exception:
        pass  # Already exists

    _log_stream_name = f"{LOG_STREAM_PREFIX}-{datetime.utcnow().strftime('%Y-%m-%d-%H%M%S')}"
    try:
        client.create_log_stream(
            logGroupName=LOG_GROUP,
            logStreamName=_log_stream_name,
        )
    except Exception:
        pass  # Already exists

    return _log_stream_name


def publish_command_metric(
    intent_name: str,
    success: bool,
    latency_ms: float,
    confidence: float = 1.0,
    tier: int = 1,
) -> None:
    """
    Publishes voice command metrics to CloudWatch asynchronously.
    Called after every command execution.
    """
    def _publish():
        client = _get_cw_client()
        if not client:
            return

        try:
            timestamp = datetime.utcnow()
            metric_data = [
                # Command count (success/failure)
                {
                    "MetricName": "CommandCount",
                    "Timestamp": timestamp,
                    "Value": 1,
                    "Unit": "Count",
                    "Dimensions": [
                        {"Name": "Intent", "Value": intent_name},
                        {"Name": "Status", "Value": "Success" if success else "Failure"},
                    ],
                },
                # Latency
                {
                    "MetricName": "CommandLatency",
                    "Timestamp": timestamp,
                    "Value": latency_ms,
                    "Unit": "Milliseconds",
                    "Dimensions": [
                        {"Name": "Intent", "Value": intent_name},
                        {"Name": "Tier", "Value": f"Tier{tier}"},
                    ],
                },
                # Confidence score
                {
                    "MetricName": "IntentConfidence",
                    "Timestamp": timestamp,
                    "Value": confidence * 100,  # percentage
                    "Unit": "Percent",
                    "Dimensions": [
                        {"Name": "Intent", "Value": intent_name},
                    ],
                },
            ]

            client.put_metric_data(
                Namespace=NAMESPACE,
                MetricData=metric_data,
            )
            logger.debug("Published CloudWatch metrics for %s", intent_name)

        except Exception as exc:
            logger.debug("CloudWatch metric publish failed: %s", exc)

    # Fire and forget — don't block the voice response
    threading.Thread(target=_publish, daemon=True).start()


def log_command_event(
    utterance: str,
    intent_name: str,
    success: bool,
    message: str = "",
    latency_ms: float = 0.0,
    params: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Logs a structured voice command event to CloudWatch Logs asynchronously.
    """
    def _log():
        global _log_sequence_token
        client = _get_logs_client()
        if not client:
            return

        stream = _ensure_log_stream()
        if not stream:
            return

        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "utterance": utterance[:200],
            "intent": intent_name,
            "success": success,
            "message": message[:300],
            "latency_ms": round(latency_ms, 1),
            "params": {k: str(v)[:100] for k, v in (params or {}).items() if k != "_lang"},
        }

        try:
            put_args = {
                "logGroupName": LOG_GROUP,
                "logStreamName": stream,
                "logEvents": [
                    {
                        "timestamp": int(time.time() * 1000),
                        "message": json.dumps(event),
                    }
                ],
            }
            if _log_sequence_token:
                put_args["sequenceToken"] = _log_sequence_token

            response = client.put_log_events(**put_args)
            _log_sequence_token = response.get("nextSequenceToken")
            logger.debug("Logged command event to CloudWatch Logs")

        except Exception as exc:
            logger.debug("CloudWatch Logs publish failed: %s", exc)

    threading.Thread(target=_log, daemon=True).start()


def track_command(
    utterance: str,
    intent_name: str,
    success: bool,
    message: str = "",
    latency_ms: float = 0.0,
    confidence: float = 1.0,
    tier: int = 1,
    params: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Unified entry point: publishes both metrics and structured logs.
    Call this after every command execution.
    """
    publish_command_metric(intent_name, success, latency_ms, confidence, tier)
    log_command_event(utterance, intent_name, success, message, latency_ms, params)
