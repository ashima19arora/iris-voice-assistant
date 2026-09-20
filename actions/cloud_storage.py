"""
Iris Amazon S3 Cloud Storage — Voice-Powered Screenshot & File Cloud Backup
============================================================================
WHAT THIS FILE DOES (Simple English):
  Enables users to save screenshots and files to the cloud with voice commands like
  "save screenshot to cloud" or "backup this to cloud". Files are uploaded to Amazon S3
  with organized prefixes (screenshots/, files/) and automatic timestamped naming.

GREAT TECH & PACKAGES USED IN THIS FILE:
  - Amazon S3 (Simple Storage Service):
      * What it does: Unlimited, durable cloud object storage.
      * Why we use it: Gives Iris users instant cloud backup of screenshots and files,
        accessible from any device. Shows real cloud persistence beyond local disk.
  - boto3 (AWS SDK for Python):
      * What it does: Official AWS API client.
      * Why we use it: Direct S3 upload with server-side encryption and metadata tagging.
"""

from __future__ import annotations

import io
import os
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from .feedback import speak, notify

logger = logging.getLogger("IrisS3Cloud")

REGION_NAME = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("IRIS_S3_BUCKET", "iris-voice-assistant-cloud")

_s3_client = None
_client_lock = threading.Lock()


def get_s3_client():
    """Returns a cached boto3 S3 client if real AWS credentials exist."""
    global _s3_client
    with _client_lock:
        if _s3_client is None:
            key = os.getenv("AWS_ACCESS_KEY_ID", "")
            if not key or key.startswith("your_") or key == "test":
                return None
            try:
                import boto3
                _s3_client = boto3.client("s3", region_name=REGION_NAME)
            except Exception as exc:
                logger.debug("Could not initialize Amazon S3 client: %s", exc)
                return None
    return _s3_client


def _ensure_bucket_exists(client) -> bool:
    """Creates the S3 bucket if it doesn't exist (idempotent)."""
    try:
        client.head_bucket(Bucket=S3_BUCKET_NAME)
        return True
    except Exception:
        try:
            create_params = {"Bucket": S3_BUCKET_NAME}
            if REGION_NAME != "us-east-1":
                create_params["CreateBucketConfiguration"] = {
                    "LocationConstraint": REGION_NAME
                }
            client.create_bucket(**create_params)
            logger.info("Created S3 bucket: %s", S3_BUCKET_NAME)
            return True
        except Exception as exc:
            logger.warning("Could not create S3 bucket: %s", exc)
            return False


def upload_screenshot_to_s3(lang: str = "en") -> Tuple[bool, str]:
    """
    Takes a screenshot and uploads it to S3.
    Returns (success, s3_key_or_error_message).
    """
    client = get_s3_client()
    if not client:
        notify("S3 cloud storage not configured", success=False)
        speak(
            "क्लाउड स्टोरेज उपलब्ध नहीं है" if lang == "hi"
            else "Cloud storage is not configured.",
            lang=lang,
        )
        return False, "S3 client not available"

    try:
        import pyautogui
        from PIL import Image

        # Capture screenshot
        screenshot = pyautogui.screenshot()
        buffer = io.BytesIO()
        screenshot.save(buffer, format="PNG", optimize=True)
        buffer.seek(0)

        # Generate timestamped key
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        s3_key = f"screenshots/iris-screenshot-{timestamp}.png"

        # Ensure bucket exists and upload
        _ensure_bucket_exists(client)
        client.upload_fileobj(
            buffer,
            S3_BUCKET_NAME,
            s3_key,
            ExtraArgs={
                "ContentType": "image/png",
                "ServerSideEncryption": "AES256",
                "Metadata": {
                    "source": "iris-voice-assistant",
                    "captured-at": timestamp,
                },
            },
        )

        s3_url = f"s3://{S3_BUCKET_NAME}/{s3_key}"
        logger.info("Screenshot uploaded to S3: %s", s3_url)
        notify(f"☁️ Screenshot saved to cloud: {s3_key}")
        speak(
            "स्क्रीनशॉट क्लाउड पर सेव हो गया" if lang == "hi"
            else "Screenshot saved to cloud.",
            lang=lang,
        )
        return True, s3_key

    except Exception as exc:
        logger.error("S3 screenshot upload failed: %s", exc)
        notify(f"Cloud upload failed: {exc}", success=False)
        speak(
            "क्लाउड अपलोड नहीं हो पाया" if lang == "hi"
            else "Sorry, cloud upload failed.",
            lang=lang,
        )
        return False, str(exc)


def upload_file_to_s3(
    file_path: str, lang: str = "en"
) -> Tuple[bool, str]:
    """
    Uploads a local file to S3.
    Returns (success, s3_key_or_error_message).
    """
    client = get_s3_client()
    if not client:
        return False, "S3 client not available"

    path = Path(file_path)
    if not path.exists():
        speak("File not found." if lang != "hi" else "फ़ाइल नहीं मिली।", lang=lang)
        return False, f"File not found: {file_path}"

    try:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        s3_key = f"files/{timestamp}_{path.name}"

        _ensure_bucket_exists(client)
        client.upload_file(
            str(path),
            S3_BUCKET_NAME,
            s3_key,
            ExtraArgs={
                "ServerSideEncryption": "AES256",
                "Metadata": {
                    "source": "iris-voice-assistant",
                    "original-name": path.name,
                },
            },
        )

        logger.info("File uploaded to S3: %s → %s", path.name, s3_key)
        notify(f"☁️ File saved to cloud: {s3_key}")
        speak(
            f"{path.name} क्लाउड पर सेव हो गया" if lang == "hi"
            else f"File {path.name} saved to cloud.",
            lang=lang,
        )
        return True, s3_key

    except Exception as exc:
        logger.error("S3 file upload failed: %s", exc)
        return False, str(exc)
