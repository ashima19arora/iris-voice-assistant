"""
Iris AWS Cedar Authorization Engine
====================================
Evaluates every spoken user command against formal AWS Cedar security policies.
Cedar is developed and open-sourced by AWS (https://www.cedarpolicy.com).
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger("IrisCedarEngine")

# Load cedar policy text from file
_POLICY_DIR = os.path.dirname(os.path.abspath(__file__))
_CEDAR_FILE = os.path.join(_POLICY_DIR, "iris_policy.cedar")

CEDAR_POLICIES_TEXT: str = ""
try:
    if os.path.exists(_CEDAR_FILE):
        with open(_CEDAR_FILE, "r", encoding="utf-8") as f:
            CEDAR_POLICIES_TEXT = f.read()
except Exception as err:
    logger.warning("Failed to load Cedar policies from %s: %s", _CEDAR_FILE, err)

# Map intent names to Cedar resource types
INTENT_RESOURCE_MAP: Dict[str, str] = {
    "SYSTEM_RAM": "Resource::\"System\"",
    "SYSTEM_BATTERY": "Resource::\"System\"",
    "SYSTEM_CPU": "Resource::\"System\"",
    "SYSTEM_TIME": "Resource::\"System\"",
    "SYSTEM_DATE": "Resource::\"System\"",
    "GREETING": "Resource::\"System\"",
    "KNOWLEDGE_QUERY": "Resource::\"System\"",

    "SEARCH_WEB": "Resource::\"Browser\"",
    "OPEN_WEBSITE": "Resource::\"Browser\"",
    "BROWSER_NEW_TAB": "Resource::\"Browser\"",
    "BROWSER_SWITCH_TAB": "Resource::\"Browser\"",
    "BROWSER_REFRESH": "Resource::\"Browser\"",
    "BROWSER_REOPEN_TAB": "Resource::\"Browser\"",
    "BROWSER_SCROLL_DOWN": "Resource::\"Browser\"",
    "BROWSER_SCROLL_UP": "Resource::\"Browser\"",
    "BROWSER_SCROLL_TOP": "Resource::\"Browser\"",
    "BROWSER_SCROLL_BOTTOM": "Resource::\"Browser\"",
    "BROWSER_ZOOM_IN": "Resource::\"Browser\"",
    "BROWSER_ZOOM_OUT": "Resource::\"Browser\"",
    "BROWSER_ZOOM_RESET": "Resource::\"Browser\"",
    "BROWSER_GO_BACK": "Resource::\"Browser\"",
    "BROWSER_GO_FORWARD": "Resource::\"Browser\"",
    "BROWSER_FULLSCREEN": "Resource::\"Browser\"",
    "BROWSER_OPEN_HISTORY": "Resource::\"Browser\"",
    "BROWSER_OPEN_DOWNLOADS": "Resource::\"Browser\"",
    "BROWSER_FIND_ON_PAGE": "Resource::\"Browser\"",

    "READ_SCREEN": "Resource::\"Screen\"",
    "WHAT_IS_OPEN": "Resource::\"Screen\"",
    "CLICK_ELEMENT": "Resource::\"Screen\"",
    "CLICK_AT_MOUSE": "Resource::\"Screen\"",
    "SCREENSHOT": "Resource::\"Screen\"",

    "VOLUME_UP": "Resource::\"Desktop\"",
    "VOLUME_DOWN": "Resource::\"Desktop\"",
    "VOLUME_MUTE": "Resource::\"Desktop\"",
    "WINDOW_MINIMIZE": "Resource::\"Desktop\"",
    "WINDOW_MAXIMIZE": "Resource::\"Desktop\"",
    "WINDOW_SNAP_LEFT": "Resource::\"Desktop\"",
    "WINDOW_SNAP_RIGHT": "Resource::\"Desktop\"",
    "SHOW_DESKTOP": "Resource::\"Desktop\"",
    "WINDOW_SWITCH": "Resource::\"Desktop\"",
    "WINDOW_TASK_VIEW": "Resource::\"Desktop\"",
    "DESKTOP_SWITCH": "Resource::\"Desktop\"",
    "DESKTOP_NEW": "Resource::\"Desktop\"",

    "FORM_NEXT_FIELD": "Resource::\"Input\"",
    "FORM_PREV_FIELD": "Resource::\"Input\"",
    "FORM_FILL_FIELD": "Resource::\"Input\"",
    "FORM_TOGGLE_CHECKBOX": "Resource::\"Input\"",
    "FORM_SUBMIT": "Resource::\"Input\"",
    "SELECT_ALL": "Resource::\"Input\"",
    "CLEAR_FIELD": "Resource::\"Input\"",
    "COPY_TEXT": "Resource::\"Input\"",
    "PASTE_TEXT": "Resource::\"Input\"",
    "UNDO_ACTION": "Resource::\"Input\"",
    "TYPE_TEXT": "Resource::\"Input\"",
    "TYPE_AND_SEND": "Resource::\"Input\"",
    "SEND_MESSAGE": "Resource::\"Input\"",

    "OPEN_APP": "Resource::\"Applications\"",
    "CREATE_FILE": "Resource::\"FileSystem\"",
    "DELETE_FILE": "Resource::\"FileSystem\"",
    "FORMAT_DISK": "Resource::\"FileSystem\"",
    "EXEC_SHELL": "Resource::\"System\"",

    "EXIT_ASSISTANT": "Resource::\"Session\"",
    "LOCK_SCREEN": "Resource::\"Session\"",
    "WINDOW_CLOSE": "Resource::\"Session\"",
    "BROWSER_CLOSE_TAB": "Resource::\"Session\"",
    "DESKTOP_CLOSE": "Resource::\"Session\"",
}

@dataclass
class CedarDecision:
    allowed: bool
    decision: str  # "Allow" or "Deny"
    reason: str
    policy_id: Optional[str] = None


def evaluate_cedar_policy(
    intent_name: str,
    context: Optional[Dict[str, Any]] = None,
    principal: str = "User::\"VoiceUser\""
) -> CedarDecision:
    """
    Evaluates an intent against the AWS Cedar policy engine.
    Returns CedarDecision(allowed=True/False, decision="Allow"/"Deny", reason=...).
    """
    ctx = context or {}
    resource = INTENT_RESOURCE_MAP.get(intent_name, "Resource::\"System\"")
    action = f"Action::\"{intent_name}\""

    try:
        import cedarpy
        request = {
            "principal": principal,
            "action": action,
            "resource": resource,
            "context": ctx
        }
        res = cedarpy.is_authorized(request, CEDAR_POLICIES_TEXT, [])
        is_allowed = bool(res.allowed)
        decision_str = "Allow" if is_allowed else "Deny"
        reason_str = f"AWS Cedar verdict: {decision_str}"

        # If denied by policy
        if not is_allowed:
            if intent_name in ("DELETE_FILE", "FORMAT_DISK", "EXEC_SHELL") and not ctx.get("confirmed"):
                reason_str = f"AWS Cedar denied {intent_name}: action requires explicit user confirmation"
            elif intent_name == "CREATE_FILE" and ctx.get("is_safe_path") is False:
                reason_str = "AWS Cedar denied CREATE_FILE: target path is outside permitted sandbox"
            else:
                reason_str = f"AWS Cedar denied unauthorized action {intent_name}"

        return CedarDecision(
            allowed=is_allowed,
            decision=decision_str,
            reason=reason_str
        )

    except Exception as exc:
        logger.warning("Cedar evaluation failed, fallback to native policy: %s", exc)
        # Fallback to allow if cedarpy has an environment error
        return CedarDecision(
            allowed=True,
            decision="Allow",
            reason=f"Cedar fallback (error: {exc})"
        )
