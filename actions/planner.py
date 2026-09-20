"""Tier-2 planner: OpenRouter native tool-calling bound to TOOL_REGISTRY schemas."""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from .config import MAX_PLANNER_TOOL_CALLS, OPENROUTER_PLANNER_MODEL, PLANNER_TIMEOUT_SEC
from .llm_client import key_manager
from .tools.registry import (
    TOOL_REGISTRY,
    assert_call_budget,
    build_tool_contracts,
    execute_tool,
    openai_tool_schemas,
)

logger = logging.getLogger("iris")

PLANNER_SYSTEM = (
    "You are Iris, a smart, concise Windows accessibility voice assistant planner. "
    "Call tools from the provided schema only. Never invent tool names. "
    "Rules: "
    "1) Only call app_launch if the user explicitly commanded to launch an OS application like notepad, calculator, task manager, edge, chrome, vscode. Never guess or batch launch multiple apps. "
    "2) EXPLICIT WEB SEARCH: ONLY call search_web or browser_navigate if the user explicitly commanded to search the web or open a site (e.g. 'search web for X', 'search for X on Google', 'open youtube.com'). NEVER call search_web for factual questions, general knowledge, definitions, math, or conversational inquiries. "
    "3) To click a visible link, button, or search result on the screen, call click_on_screen with the target text. "
    "4) To create notes or files, call fs_create_file with filename, location ('desktop'), and content. "
    "5) Keep tool calls minimal: at most 1 or 2 tools. Do not chain repeated failed attempts. "
    "6) PUNCHY & CONCISE: In your spoken response, always prefer a punchy one-liner or short 1-to-2 sentence spoken answer. Never give long, robotic explanations. "
    "7) QUESTIONS & CONVERSATIONAL Q&A: For any factual question, definition, calculation, explanation, or small talk (e.g. 'what is X', 'who is Y', 'how does Z work', 'capital of France', 'apple kya hai', 'can you speak Hindi', 'tum kaise ho'): DO NOT CALL search_web! DO NOT OPEN ANY BROWSER! Either call knowledge_answer or answer the user directly with natural speech in their language (Hindi if Hindi, English if English)."
)


class PlannerFailure(Exception):
    def __init__(self, kind: str, spoken: str):
        super().__init__(spoken)
        self.kind = kind
        self.spoken = spoken


def schemas_from_registry() -> List[Dict[str, Any]]:
    """Same function chain as execution: build_tool_contracts → openai_tool_schemas."""
    assert build_tool_contracts().keys() == TOOL_REGISTRY.keys()
    return openai_tool_schemas()


def default_tool_complete(
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    *,
    timeout: float = PLANNER_TIMEOUT_SEC,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """POST chat/completions with tools=. Returns the raw JSON body."""
    keys = [api_key] if api_key is not None else key_manager.get_candidate_keys()
    if not keys:
        raise PlannerFailure("invalid_api_key", "I don't have a working AI key right now.")
    last_status = None
    for key in keys:
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://iris.local",
            "X-Title": "Iris Planner",
        }
        payload = {
            "model": OPENROUTER_PLANNER_MODEL,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.1,
            "max_tokens": 400,
        }
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
        except requests.Timeout as exc:
            logger.error("planner network timeout: %s", exc)
            raise PlannerFailure("timeout", "The planning request timed out.") from exc
        except requests.RequestException as exc:
            logger.error("planner network error: %s", exc)
            raise PlannerFailure("timeout", "I could not reach the planner network.") from exc
        last_status = response.status_code
        if response.status_code in (401, 403):
            key_manager.mark_failure(key, status_code=response.status_code)
            logger.error("planner invalid API key status %s", response.status_code)
            raise PlannerFailure("invalid_api_key", "The planner API key is invalid or expired.")
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError as exc:
                logger.error("planner malformed JSON body")
                raise PlannerFailure("malformed_json", "The planner returned unreadable data.") from exc
        if response.status_code == 429:
            key_manager.mark_failure(key, status_code=429)
            continue
    raise PlannerFailure("invalid_api_key", "The planner API key is invalid or expired.")


def _extract_tool_calls(message: Dict[str, Any]) -> List[Dict[str, Any]]:
    return message.get("tool_calls") or []


def run_planner(
    utterance: str,
    context: Dict[str, Any],
    *,
    complete_fn: Callable = default_tool_complete,
    confirm_fn=None,
    lang: str = "en",
) -> Dict[str, Any]:
    tools = schemas_from_registry()
    system_prompt = PLANNER_SYSTEM
    if lang == "hi":
        system_prompt += (
            " LANGUAGE REQUIREMENT: The user's active language is Hindi (हिन्दी). "
            "You MUST speak your final response in clear, conversational Hindi in Devanagari script. "
            "Never reply in English when the user is in Hindi mode."
        )
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps({"utterance": utterance, "context": context, "lang": lang}, default=str)[:8000],
        },
    ]
    steps: List[Dict[str, Any]] = []
    call_count = 0
    raw_last: Dict[str, Any] = {}

    while True:
        raw_last = complete_fn(messages, tools)
        choices = raw_last.get("choices") or []
        if not choices:
            raise PlannerFailure("malformed_json", "The planner returned an empty response.")
        message = choices[0].get("message") or {}
        tool_calls = _extract_tool_calls(message)
        if not tool_calls:
            spoken = (message.get("content") or "").strip() or "Done."
            return {"ok": True, "spoken": spoken, "steps": steps, "raw": raw_last}

        messages.append(message)
        for call in tool_calls:
            call_count += 1
            budget = assert_call_budget(call_count)
            if budget:
                steps.append({"index": call_count, "tool": call.get("function", {}).get("name"), "ok": False, "error": budget})
                return {
                    "ok": False,
                    "spoken": "I stopped because the plan was too long.",
                    "steps": steps,
                    "raw": raw_last,
                }
            fn = call.get("function") or {}
            name = fn.get("name") or ""
            try:
                arguments = json.loads(fn.get("arguments") or "{}")
                if not isinstance(arguments, dict):
                    raise ValueError("arguments not an object")
            except (json.JSONDecodeError, ValueError) as exc:
                logger.error("malformed tool arguments: %s", exc)
                raise PlannerFailure("malformed_json", "The planner returned a broken tool call.") from exc
            if name not in TOOL_REGISTRY:
                logger.error("hallucinated tool %s", name)
                result = {"ok": False, "error": f"Unknown tool '{name}'."}
                steps.append({"index": call_count, "tool": name, "ok": False, "error": result["error"]})
                raise PlannerFailure("unknown_tool", f"I don't have a tool called {name}.")
            result = execute_tool(name, arguments, confirm_fn=confirm_fn)
            steps.append({"index": call_count, "tool": name, "ok": bool(result.get("ok")), "error": result.get("error") or "", "result": result})
            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id") or f"call_{call_count}",
                "content": json.dumps(result, default=str)[:4000],
            })
