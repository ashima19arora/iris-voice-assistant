"""
Iris Amazon DynamoDB Security Audit Ledger
===========================================
Persists every voice command, detected intent, Cedar authorization verdict,
and execution outcome to Amazon DynamoDB (or LocalStack on localhost:4566).
Runs asynchronously in a background thread to ensure zero audio latency.
"""

from __future__ import annotations

import os
import json
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("IrisDynamoLogger")

TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "IrisSecurityAudit")
ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL", os.getenv("LOCALSTACK_ENDPOINT_URL", None))
REGION_NAME = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

_dynamo_resource = None
_table_initialized = False
_init_lock = threading.Lock()


def get_dynamo_resource():
    """Returns a cached boto3 DynamoDB resource."""
    global _dynamo_resource
    if _dynamo_resource is None:
        try:
            import boto3
            kwargs: Dict[str, Any] = {"region_name": REGION_NAME}
            if ENDPOINT_URL:
                kwargs["endpoint_url"] = ENDPOINT_URL
            
            # Default dummy credentials for LocalStack if not provided
            if not os.getenv("AWS_ACCESS_KEY_ID") and ENDPOINT_URL:
                kwargs["aws_access_key_id"] = "test"
                kwargs["aws_secret_access_key"] = "test"

            _dynamo_resource = boto3.resource("dynamodb", **kwargs)
        except Exception as exc:
            logger.debug("Could not initialize boto3 DynamoDB resource: %s", exc)
    return _dynamo_resource


def ensure_audit_table():
    """Ensures the DynamoDB audit table exists on LocalStack or AWS."""
    global _table_initialized
    with _init_lock:
        if _table_initialized:
            return True
        resource = get_dynamo_resource()
        if not resource:
            return False
        try:
            existing = [t.name for t in resource.tables.all()]
            if TABLE_NAME not in existing:
                logger.info("Creating DynamoDB table: %s", TABLE_NAME)
                table = resource.create_table(
                    TableName=TABLE_NAME,
                    KeySchema=[
                        {"AttributeName": "session_id", "KeyType": "HASH"},
                        {"AttributeName": "timestamp", "KeyType": "RANGE"}
                    ],
                    AttributeDefinitions=[
                        {"AttributeName": "session_id", "AttributeType": "S"},
                        {"AttributeName": "timestamp", "AttributeType": "S"}
                    ],
                    BillingMode="PAY_PER_REQUEST"
                )
                table.wait_until_exists()
            _table_initialized = True
            return True
        except Exception as exc:
            logger.debug("DynamoDB table check failed (service may be offline): %s", exc)
            return False


def put_audit_event_async(event: Dict[str, Any]):
    """Dispatches a DynamoDB put_item asynchronously in a background thread."""
    def _worker():
        try:
            resource = get_dynamo_resource()
            if not resource:
                return

            if not _table_initialized:
                if not ensure_audit_table():
                    return

            table = resource.Table(TABLE_NAME)
            # Standardize item schema
            item = {
                "session_id": event.get("session_id", datetime.now().strftime("SESSION#%Y-%m-%d")),
                "timestamp": event.get("timestamp", datetime.now().isoformat()),
                "utterance": event.get("utterance", ""),
                "intent": event.get("intent", ""),
                "tier": str(event.get("tier", "")),
                "outcome": event.get("outcome", ""),
                "reason": event.get("reason", ""),
            }
            if event.get("details"):
                # Clean nested dict for DynamoDB
                item["details"] = json.dumps(event["details"])
            
            table.put_item(Item=item)
            logger.debug("Persisted audit event to DynamoDB table %s", TABLE_NAME)
        except Exception as exc:
            logger.debug("DynamoDB async put failed: %s", exc)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
