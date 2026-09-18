"""
Single source of truth for planner tools: schemas, handlers, and SAFE/SENSITIVE class.

build_tool_contracts() returns the dict used both to generate OpenAI tool schemas
and to dispatch execution. Do not maintain a second hand-written tool list.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Literal, Optional

from ..confirmation import request_confirmation
from ..config import MAX_PLANNER_TOOL_CALLS
from ..security.sanitizer import sanitize_app_target, sanitize_url, sanitize_typed_text

logger = logging.getLogger("iris")

Safety = Literal["SAFE", "SENSITIVE"]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]
    safety: Safety
    handler: Callable[[Dict[str, Any]], Dict[str, Any]]


def _tool_fs_list(args: Dict[str, Any]) -> Dict[str, Any]:
    from ..context_provider import fs_list_directory
    loc = str(args.get("location") or "desktop")
    if ".." in loc.replace("\\", "/") or "\x00" in loc:
        logger.warning("validation rejection: fs_list_directory location %r", loc)
        return {"ok": False, "error": "Path traversal is not allowed."}
    return fs_list_directory(loc)


def _tool_fs_create(args: Dict[str, Any]) -> Dict[str, Any]:
    from ..file_actions import create_file, validate_file_name
    filename = str(args.get("filename") or "")
    location = str(args.get("location") or "desktop")
    content = str(args.get("content") or "")
    ok, _, reason = validate_file_name(filename)
    if not ok:
        logger.warning("validation rejection: fs_create_file %s", reason)
        return {"ok": False, "error": reason}
    if ".." in location.replace("\\", "/"):
        logger.warning("validation rejection: fs_create_file location %r", location)
        return {"ok": False, "error": "Path traversal is not allowed."}
    success = create_file(
        filename,
        content=content,
        location=location,
        open_after=False,
        confirm_fn=lambda *a, **k: True,
    )
    return {"ok": success, "error": "" if success else "File was not created."}


def _tool_browser_navigate(args: Dict[str, Any]) -> Dict[str, Any]:
    from ..browser_actions import open_url
    raw = str(args.get("url") or args.get("target") or "")
    ok, url, reason = sanitize_url(raw)
    if not ok:
        logger.warning("validation rejection: browser_navigate %s", reason)
        return {"ok": False, "error": reason}
    try:
        success = open_url(url)
        return {"ok": bool(success), "url": url, "error": "" if success else "Could not open that page."}
    except Exception as exc:
        logger.error("browser_navigate failed: %s", exc)
        return {"ok": False, "error": "Could not open that page."}


def _tool_search_web(args: Dict[str, Any]) -> Dict[str, Any]:
    from ..browser_actions import search_web
    from ..security.sanitizer import sanitize_search_query
    query = str(args.get("query") or "")
    ok, clean, reason = sanitize_search_query(query)
    if not ok:
        logger.warning("validation rejection: search_web %s", reason)
        return {"ok": False, "error": reason}
    success = search_web(clean)
    return {"ok": bool(success), "query": clean, "error": "" if success else "Search failed."}


def _tool_click_on_screen(args: Dict[str, Any]) -> Dict[str, Any]:
    from ..screen_actions import click_element
    target = str(args.get("target") or "").strip()
    if not target or "\x00" in target:
        logger.warning("validation rejection: empty click target")
        return {"ok": False, "error": "Invalid click target."}
    nth = int(args.get("nth") or 1)
    success = click_element(target, nth=nth)
    return {"ok": bool(success), "error": "" if success else "I could not find that on screen."}


def _tool_browser_click(args: Dict[str, Any]) -> Dict[str, Any]:
    from .. import browser_runtime
    selector = str(args.get("selector") or "")
    if not selector or "\x00" in selector:
        logger.warning("validation rejection: empty/malformed selector")
        return {"ok": False, "error": "Invalid selector."}
    try:
        return {**browser_runtime.click(selector), "error": ""}
    except Exception as exc:
        logger.error("browser_click failed: %s", exc)
        return {"ok": False, "error": "Could not click that element."}


def _tool_browser_fill(args: Dict[str, Any]) -> Dict[str, Any]:
    from .. import browser_runtime
    selector = str(args.get("selector") or "")
    value = str(args.get("value") or "")
    ok, clean, reason = sanitize_typed_text(value)
    if not selector or not ok:
        logger.warning("validation rejection: browser_fill_field %s", reason)
        return {"ok": False, "error": reason or "Invalid fill arguments."}
    try:
        return {**browser_runtime.fill(selector, clean), "error": ""}
    except Exception as exc:
        logger.error("browser_fill_field failed: %s", exc)
        return {"ok": False, "error": "Could not fill that field."}


def _tool_browser_submit(args: Dict[str, Any]) -> Dict[str, Any]:
    from .. import browser_runtime
    selector = str(args.get("selector") or "form")
    try:
        return {**browser_runtime.submit(selector), "error": ""}
    except Exception as exc:
        logger.error("browser_submit failed: %s", exc)
        return {"ok": False, "error": "Could not submit the form."}


def _tool_app_launch(args: Dict[str, Any]) -> Dict[str, Any]:
    from ..system_actions import open_app
    name = str(args.get("app_name") or "")
    ok, _target, reason = sanitize_app_target(name)
    if not ok:
        logger.warning("validation rejection: app_launch %s", reason)
        return {"ok": False, "error": reason}
    success = open_app(name)
    return {"ok": success, "error": "" if success else "Could not launch the app."}


def _tool_send_message(args: Dict[str, Any]) -> Dict[str, Any]:
    from .. import form_actions
    text = str(args.get("text") or "")
    ok, clean, reason = sanitize_typed_text(text)
    if not ok or not clean:
        logger.warning("validation rejection: send_message %s", reason)
        return {"ok": False, "error": reason or "Empty message."}
    typed = form_actions.fill_field(clean, press_enter_after=True)
    return {"ok": bool(typed), "error": "" if typed else "Could not send the message."}


def _tool_knowledge(args: Dict[str, Any]) -> Dict[str, Any]:
    from ..knowledge_actions import answer_knowledge_query
    query = str(args.get("query") or "").strip()
    if not query:
        return {"ok": False, "error": "Empty question."}
    ans = answer_knowledge_query(query, lang=str(args.get("lang") or "en"), speak_answer=False)
    return {"ok": bool(ans), "answer": str(ans), "error": "" if ans else "No answer."}


def _tool_screen_inspect(args: Dict[str, Any]) -> Dict[str, Any]:
    from ..screen_understanding import describe_screen
    spoken = describe_screen(speak_aloud=False)
    return {"ok": True, "description": spoken}


def _tool_get_running_apps(args: Dict[str, Any]) -> Dict[str, Any]:
    from ..screen_understanding import get_background_apps, get_active_window_info
    return {
        "ok": True,
        "active_window": get_active_window_info(),
        "background_apps": get_background_apps(),
    }


def build_tool_contracts() -> Dict[str, ToolSpec]:
    """THE function that builds both LLM schemas and runtime dispatch."""
    return {
        "browser_navigate": ToolSpec(
            "browser_navigate",
            "Open a website in the user's real default browser (Chrome/Edge). Use for any site or Play Store link.",
            {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
            "SAFE",
            _tool_browser_navigate,
        ),
        "search_web": ToolSpec(
            "search_web",
            "Google-search a query in the user's real browser. Use this for unknown apps/sites (e.g. Aarogya Setu).",
            {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            "SAFE",
            _tool_search_web,
        ),
        "click_on_screen": ToolSpec(
            "click_on_screen",
            "Click visible text on the user's actual screen (OCR). Use for 'click the first result' / a named link.",
            {
                "type": "object",
                "properties": {
                    "target": {"type": "string"},
                    "nth": {"type": "integer", "minimum": 1, "maximum": 5},
                },
                "required": ["target"],
            },
            "SAFE",
            _tool_click_on_screen,
        ),
        "browser_click": ToolSpec(
            "browser_click",
            "Click a Playwright selector on the current page.",
            {"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]},
            "SENSITIVE",
            _tool_browser_click,
        ),
        "browser_fill_field": ToolSpec(
            "browser_fill_field",
            "Type into a form field identified by selector.",
            {
                "type": "object",
                "properties": {"selector": {"type": "string"}, "value": {"type": "string"}},
                "required": ["selector", "value"],
            },
            "SENSITIVE",
            _tool_browser_fill,
        ),
        "browser_submit": ToolSpec(
            "browser_submit",
            "Submit a form on the current page.",
            {"type": "object", "properties": {"selector": {"type": "string"}}},
            "SENSITIVE",
            _tool_browser_submit,
        ),
        "fs_list_directory": ToolSpec(
            "fs_list_directory",
            "List Desktop, Documents, or Iris using os.scandir.",
            {
                "type": "object",
                "properties": {"location": {"type": "string", "enum": ["desktop", "documents", "iris"]}},
                "required": ["location"],
            },
            "SAFE",
            _tool_fs_list,
        ),
        "fs_create_file": ToolSpec(
            "fs_create_file",
            "Create a text note in Desktop, Documents, or Iris after confirmation.",
            {
                "type": "object",
                "properties": {
                    "filename": {"type": "string"},
                    "location": {"type": "string", "enum": ["desktop", "documents", "iris"]},
                    "content": {"type": "string"},
                },
                "required": ["filename"],
            },
            "SENSITIVE",
            _tool_fs_create,
        ),
        "app_launch": ToolSpec(
            "app_launch",
            "Launch an allowlisted OS app: notepad, calculator, paint, explorer, settings, whatsapp, chrome, edge, firefox, spotify, word, excel, powerpoint, task manager, vscode, cursor. Do not pass desktop shortcut names.",
            {"type": "object", "properties": {"app_name": {"type": "string"}}, "required": ["app_name"]},
            "SAFE",
            _tool_app_launch,
        ),
        "send_message": ToolSpec(
            "send_message",
            "Send/submit the current message after confirmation.",
            {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            "SENSITIVE",
            _tool_send_message,
        ),
        "knowledge_answer": ToolSpec(
            "knowledge_answer",
            "Answer a factual question out loud.",
            {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            "SAFE",
            _tool_knowledge,
        ),
        "screen_inspect": ToolSpec(
            "screen_inspect",
            "Analyze and describe what is visible on the user's screen.",
            {"type": "object", "properties": {}},
            "SAFE",
            _tool_screen_inspect,
        ),
        "get_running_apps": ToolSpec(
            "get_running_apps",
            "List active application windows and background running applications.",
            {"type": "object", "properties": {}},
            "SAFE",
            _tool_get_running_apps,
        ),
    }


TOOL_REGISTRY: Dict[str, ToolSpec] = build_tool_contracts()
TOOL_SAFETY: Dict[str, Safety] = {name: spec.safety for name, spec in TOOL_REGISTRY.items()}


def openai_tool_schemas() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
            },
        }
        for spec in TOOL_REGISTRY.values()
    ]


def execute_tool(
    name: str,
    arguments: Dict[str, Any],
    *,
    confirm_fn=None,
    skip_confirm: bool = False,
) -> Dict[str, Any]:
    spec = TOOL_REGISTRY.get(name)
    if spec is None:
        logger.error("hallucinated tool name %r", name)
        return {"ok": False, "error": f"Unknown tool '{name}'."}
    logger.info("tool execution: %s args=%s", name, {k: v for k, v in arguments.items() if k != "_confirm_fn"})
    args = dict(arguments)
    if spec.safety == "SENSITIVE" and not skip_confirm:
        prompt = f"Allow {name}? Say yes to continue."
        fn = confirm_fn or request_confirmation
        if not fn(prompt):
            logger.info("confirmation denied for %s", name)
            return {"ok": False, "error": "Cancelled."}
        args["_confirm_fn"] = lambda *a, **k: True
    elif skip_confirm:
        args["_confirm_fn"] = lambda *a, **k: True
    elif confirm_fn is not None:
        args["_confirm_fn"] = confirm_fn
    return spec.handler(args)


def assert_call_budget(call_index: int) -> Optional[str]:
    """call_index is 1-based. Reject the 6th attempt."""
    if call_index > MAX_PLANNER_TOOL_CALLS:
        reason = f"Rejected tool call #{call_index}: max {MAX_PLANNER_TOOL_CALLS} chained calls."
        logger.error(reason)
        return reason
    return None
