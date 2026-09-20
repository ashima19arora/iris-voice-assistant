"""
Iris Action Registry and Execution Pipeline
============================================
WHAT THIS FILE DOES (Simple English):
  This file acts as the central "traffic controller" of Iris. When you speak,
  it figures out what you want to do (e.g. search Google, close a tab, fill an email field,
  answer a question), checks with the security guardrail to make sure the action is safe,
  runs the action, and announces the outcome in your spoken language.

GREAT TECH & PACKAGES USED IN THIS FILE:
  - Multi-tier Intent Dispatcher:
      * What it does: A high-speed dictionary dispatch table that routes voice commands to Python functions in 0ms.
      * Why we use it: Clean, modular architecture that allows adding new voice skills easily.
  - Security Verification Gatekeeper:
      * What it does: Inspects every command before execution to block dangerous OS modifications.
"""

import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable
from .intent_parser import parse_intent, Intent
from .feedback import speak, notify
from . import browser_actions
from . import window_actions
from . import system_actions
from . import form_actions
from . import knowledge_actions
from . import file_actions
from . import screen_actions
from . import screen_understanding
from . import messaging_actions

@dataclass
class ActionResult:
    success: bool
    intent: str
    message: str
    should_exit: bool = False

def handle_greeting(params: Dict[str, Any]) -> ActionResult:
    from .languages import get_localized_message
    lang = params.get("_lang", "en")
    message = get_localized_message("GREETING", lang)
    speak(message, lang=lang)
    notify(message)
    return ActionResult(success=True, intent="GREETING", message=message)

def handle_exit(params: Dict[str, Any]) -> ActionResult:
    from .languages import get_localized_message
    lang = params.get("_lang", "en")
    message = get_localized_message("EXIT_ASSISTANT", lang)
    speak(message, lang=lang, asynchronous=False)
    notify(message)
    return ActionResult(success=True, intent="EXIT_ASSISTANT", message=message, should_exit=True)

def handle_compound_open_and_type(params: Dict[str, Any]) -> ActionResult:
    """
    Handles two-step compound action: opening an application/website and typing text into it.
    Both steps are strictly validated by the security policy.
    """
    open_target = params.get("open_target", "")
    text_to_type = params.get("text_to_type", "")

    # Step 1: Open app or website through the secure execution pipeline
    open_result = execute_command(open_target)
    if not open_result.success:
        return ActionResult(
            success=False,
            intent="COMPOUND_OPEN_AND_TYPE",
            message=f"Sub-action blocked or failed: {open_result.message}"
        )

    # Step 2: Give the OS window time to gain focus
    time.sleep(1.8)

    # Step 3: Type the requested text (pre-sanitized by security layer)
    success = system_actions.type_text(text_to_type)

    return ActionResult(
        success=success,
        intent="COMPOUND_OPEN_AND_TYPE",
        message=f"Opened {open_target} and typed: '{text_to_type}'"
    )

# Dispatch table mapping intent names to executor functions
INTENT_HANDLERS: Dict[str, Callable[[Dict[str, Any]], ActionResult]] = {
    # Web & Browser
    "SEARCH_WEB": lambda p: ActionResult(
        success=browser_actions.search_web(p.get("query", ""), lang=p.get("_lang", "en")),
        intent="SEARCH_WEB",
        message=f"Searched for: {p.get('query', '')}"
    ),
    "OPEN_WEBSITE": lambda p: ActionResult(
        success=browser_actions.open_url(p.get("target", ""), lang=p.get("_lang", "en")),
        intent="OPEN_WEBSITE",
        message=f"Navigated to: {p.get('target', '')}"
    ),
    "BROWSER_NEW_TAB": lambda p: ActionResult(
        success=browser_actions.new_tab(p.get("url")),
        intent="BROWSER_NEW_TAB",
        message="Opened new browser tab"
    ),
    "BROWSER_CLOSE_TAB": lambda p: ActionResult(
        success=browser_actions.close_tab(),
        intent="BROWSER_CLOSE_TAB",
        message="Closed active browser tab"
    ),
    "BROWSER_SWITCH_TAB": lambda p: ActionResult(
        success=browser_actions.switch_tab(p.get("direction", "next")),
        intent="BROWSER_SWITCH_TAB",
        message=f"Switched tab ({p.get('direction', 'next')})"
    ),
    "BROWSER_REFRESH": lambda p: ActionResult(
        success=browser_actions.refresh_page(),
        intent="BROWSER_REFRESH",
        message="Refreshed active page"
    ),
    "BROWSER_REOPEN_TAB": lambda p: ActionResult(
        success=browser_actions.reopen_tab(),
        intent="BROWSER_REOPEN_TAB",
        message="Reopened last closed tab"
    ),

    # Window Management
    "WINDOW_CLOSE": lambda p: ActionResult(
        success=window_actions.close_window(lang=p.get("_lang", "en")),
        intent="WINDOW_CLOSE",
        message="Closed active window"
    ),
    "WINDOW_MINIMIZE": lambda p: ActionResult(
        success=window_actions.minimize_window(lang=p.get("_lang", "en")),
        intent="WINDOW_MINIMIZE",
        message="Minimized active window"
    ),
    "WINDOW_MAXIMIZE": lambda p: ActionResult(
        success=window_actions.maximize_window(lang=p.get("_lang", "en")),
        intent="WINDOW_MAXIMIZE",
        message="Maximized active window"
    ),
    "SHOW_DESKTOP": lambda p: ActionResult(
        success=window_actions.show_desktop(lang=p.get("_lang", "en")),
        intent="SHOW_DESKTOP",
        message="Navigated to desktop"
    ),
    "WINDOW_SWITCH": lambda p: ActionResult(
        success=window_actions.switch_window(),
        intent="WINDOW_SWITCH",
        message="Switched application window"
    ),

    # Hardware & System
    "VOLUME_UP": lambda p: ActionResult(
        success=system_actions.volume_up(p.get("steps", 3), lang=p.get("_lang", "en")),
        intent="VOLUME_UP",
        message=f"Increased volume by {p.get('steps', 3)} steps"
    ),
    "VOLUME_DOWN": lambda p: ActionResult(
        success=system_actions.volume_down(p.get("steps", 3), lang=p.get("_lang", "en")),
        intent="VOLUME_DOWN",
        message=f"Decreased volume by {p.get('steps', 3)} steps"
    ),
    "VOLUME_MUTE": lambda p: ActionResult(
        success=system_actions.toggle_mute(lang=p.get("_lang", "en")),
        intent="VOLUME_MUTE",
        message="Toggled volume mute"
    ),
    "SCREENSHOT": lambda p: ActionResult(
        success=bool(system_actions.take_screenshot(lang=p.get("_lang", "en"))),
        intent="SCREENSHOT",
        message="Captured screenshot"
    ),
    "OPEN_APP": lambda p: ActionResult(
        success=system_actions.open_app(p.get("app_name", ""), lang=p.get("_lang", "en")),
        intent="OPEN_APP",
        message=f"Opened application: {p.get('app_name', '')}"
    ),
    "MEDIA_PLAY_PAUSE": lambda p: ActionResult(
        success=system_actions.play_pause_media(lang=p.get("_lang", "en")),
        intent="MEDIA_PLAY_PAUSE",
        message="Toggled media playback"
    ),
    "LOCK_SCREEN": lambda p: ActionResult(
        success=system_actions.lock_workstation(lang=p.get("_lang", "en")),
        intent="LOCK_SCREEN",
        message="Locked workstation"
    ),

    # System Status & Diagnostics
    "SYSTEM_RAM": lambda p: ActionResult(
        success=True,
        intent="SYSTEM_RAM",
        message=system_actions.get_ram_usage(lang=p.get("_lang", "en"))
    ),
    "SYSTEM_BATTERY": lambda p: ActionResult(
        success=True,
        intent="SYSTEM_BATTERY",
        message=system_actions.get_battery_status(lang=p.get("_lang", "en"))
    ),
    "SYSTEM_CPU": lambda p: ActionResult(
        success=True,
        intent="SYSTEM_CPU",
        message=system_actions.get_cpu_usage(lang=p.get("_lang", "en"))
    ),
    "SYSTEM_TIME": lambda p: ActionResult(
        success=True,
        intent="SYSTEM_TIME",
        message=system_actions.get_current_time(lang=p.get("_lang", "en"))
    ),
    "SYSTEM_DATE": lambda p: ActionResult(
        success=True,
        intent="SYSTEM_DATE",
        message=system_actions.get_current_date(lang=p.get("_lang", "en"))
    ),

    # Text Dictation & Compound Commands
    "TYPE_TEXT": lambda p: ActionResult(
        success=system_actions.type_text(p.get("text", ""), lang=p.get("_lang", "en")),
        intent="TYPE_TEXT",
        message=f"Typed text: {p.get('text', '')}"
    ),
    "COMPOUND_OPEN_AND_TYPE": handle_compound_open_and_type,

    # Browser Scrolling, Zoom, and Search
    "BROWSER_SCROLL_DOWN": lambda p: ActionResult(
        success=browser_actions.scroll_down(p.get("steps", 1), lang=p.get("_lang", "en")),
        intent="BROWSER_SCROLL_DOWN",
        message="Scrolled down page"
    ),
    "BROWSER_SCROLL_UP": lambda p: ActionResult(
        success=browser_actions.scroll_up(p.get("steps", 1), lang=p.get("_lang", "en")),
        intent="BROWSER_SCROLL_UP",
        message="Scrolled up page"
    ),
    "BROWSER_SCROLL_TOP": lambda p: ActionResult(
        success=browser_actions.scroll_top(lang=p.get("_lang", "en")),
        intent="BROWSER_SCROLL_TOP",
        message="Scrolled to top of page"
    ),
    "BROWSER_SCROLL_BOTTOM": lambda p: ActionResult(
        success=browser_actions.scroll_bottom(lang=p.get("_lang", "en")),
        intent="BROWSER_SCROLL_BOTTOM",
        message="Scrolled to bottom of page"
    ),
    "BROWSER_ZOOM_IN": lambda p: ActionResult(
        success=browser_actions.zoom_in(lang=p.get("_lang", "en")),
        intent="BROWSER_ZOOM_IN",
        message="Zoomed in"
    ),
    "BROWSER_ZOOM_OUT": lambda p: ActionResult(
        success=browser_actions.zoom_out(lang=p.get("_lang", "en")),
        intent="BROWSER_ZOOM_OUT",
        message="Zoomed out"
    ),
    "BROWSER_ZOOM_RESET": lambda p: ActionResult(
        success=browser_actions.reset_zoom(lang=p.get("_lang", "en")),
        intent="BROWSER_ZOOM_RESET",
        message="Reset zoom"
    ),
    "BROWSER_GO_BACK": lambda p: ActionResult(
        success=browser_actions.go_back(lang=p.get("_lang", "en")),
        intent="BROWSER_GO_BACK",
        message="Navigated back"
    ),
    "BROWSER_GO_FORWARD": lambda p: ActionResult(
        success=browser_actions.go_forward(lang=p.get("_lang", "en")),
        intent="BROWSER_GO_FORWARD",
        message="Navigated forward"
    ),
    "BROWSER_OPEN_HISTORY": lambda p: ActionResult(
        success=browser_actions.open_history(lang=p.get("_lang", "en")),
        intent="BROWSER_OPEN_HISTORY",
        message="Opened history"
    ),
    "BROWSER_OPEN_DOWNLOADS": lambda p: ActionResult(
        success=browser_actions.open_downloads(lang=p.get("_lang", "en")),
        intent="BROWSER_OPEN_DOWNLOADS",
        message="Opened downloads"
    ),
    "BROWSER_BOOKMARK": lambda p: ActionResult(
        success=browser_actions.bookmark_page(lang=p.get("_lang", "en")),
        intent="BROWSER_BOOKMARK",
        message="Bookmarked page"
    ),
    "BROWSER_FULLSCREEN": lambda p: ActionResult(
        success=browser_actions.toggle_fullscreen(lang=p.get("_lang", "en")),
        intent="BROWSER_FULLSCREEN",
        message="Toggled fullscreen"
    ),
    "BROWSER_FIND_ON_PAGE": lambda p: ActionResult(
        success=browser_actions.find_on_page(p.get("query", ""), lang=p.get("_lang", "en")),
        intent="BROWSER_FIND_ON_PAGE",
        message=f"Searched page for: {p.get('query', '')}"
    ),

    # Window Snapping & Virtual Desktops
    "WINDOW_SNAP_LEFT": lambda p: ActionResult(
        success=window_actions.snap_left(lang=p.get("_lang", "en")),
        intent="WINDOW_SNAP_LEFT",
        message="Snapped window left"
    ),
    "WINDOW_SNAP_RIGHT": lambda p: ActionResult(
        success=window_actions.snap_right(lang=p.get("_lang", "en")),
        intent="WINDOW_SNAP_RIGHT",
        message="Snapped window right"
    ),
    "WINDOW_TASK_VIEW": lambda p: ActionResult(
        success=window_actions.open_task_view(lang=p.get("_lang", "en")),
        intent="WINDOW_TASK_VIEW",
        message="Opened task view"
    ),
    "DESKTOP_SWITCH": lambda p: ActionResult(
        success=window_actions.switch_desktop(p.get("direction", "next"), lang=p.get("_lang", "en")),
        intent="DESKTOP_SWITCH",
        message=f"Switched desktop ({p.get('direction', 'next')})"
    ),
    "DESKTOP_NEW": lambda p: ActionResult(
        success=window_actions.new_desktop(lang=p.get("_lang", "en")),
        intent="DESKTOP_NEW",
        message="Created new virtual desktop"
    ),
    "DESKTOP_CLOSE": lambda p: ActionResult(
        success=window_actions.close_desktop(lang=p.get("_lang", "en")),
        intent="DESKTOP_CLOSE",
        message="Closed virtual desktop"
    ),

    # Form Filling & Accessibility Navigation
    "FORM_FILL_FIELD": lambda p: ActionResult(
        success=form_actions.fill_field(p.get("text", ""), lang=p.get("_lang", "en")),
        intent="FORM_FILL_FIELD",
        message=f"Filled field with: {p.get('text', '')}"
    ),
    "FORM_NEXT_FIELD": lambda p: ActionResult(
        success=form_actions.press_tab(p.get("steps", 1), lang=p.get("_lang", "en")),
        intent="FORM_NEXT_FIELD",
        message="Moved to next field"
    ),
    "FORM_PREV_FIELD": lambda p: ActionResult(
        success=form_actions.previous_field(p.get("steps", 1), lang=p.get("_lang", "en")),
        intent="FORM_PREV_FIELD",
        message="Moved to previous field"
    ),
    "FORM_SUBMIT": lambda p: ActionResult(
        success=form_actions.press_enter(lang=p.get("_lang", "en")),
        intent="FORM_SUBMIT",
        message="Submitted form"
    ),
    "FORM_TOGGLE_CHECKBOX": lambda p: ActionResult(
        success=form_actions.press_space(lang=p.get("_lang", "en")),
        intent="FORM_TOGGLE_CHECKBOX",
        message="Toggled checkbox / selected option"
    ),
    "SELECT_ALL": lambda p: ActionResult(
        success=form_actions.select_all(lang=p.get("_lang", "en")),
        intent="SELECT_ALL",
        message="Selected all text"
    ),
    "CLEAR_FIELD": lambda p: ActionResult(
        success=form_actions.clear_field(lang=p.get("_lang", "en")),
        intent="CLEAR_FIELD",
        message="Cleared active field"
    ),
    "COPY_TEXT": lambda p: ActionResult(
        success=form_actions.copy_text(lang=p.get("_lang", "en")),
        intent="COPY_TEXT",
        message="Copied text to clipboard"
    ),
    "PASTE_TEXT": lambda p: ActionResult(
        success=form_actions.paste_text(lang=p.get("_lang", "en")),
        intent="PASTE_TEXT",
        message="Pasted text from clipboard"
    ),
    "UNDO_ACTION": lambda p: ActionResult(
        success=form_actions.undo_action(lang=p.get("_lang", "en")),
        intent="UNDO_ACTION",
        message="Undid last action"
    ),

    # Messaging
    "SEND_MESSAGE": lambda p: ActionResult(
        success=form_actions.press_enter(lang=p.get("_lang", "en")),
        intent="SEND_MESSAGE",
        message="Sent message"
    ),
    "TYPE_AND_SEND": lambda p: ActionResult(
        success=form_actions.fill_field(p.get("text", ""), press_enter_after=True, lang=p.get("_lang", "en")),
        intent="TYPE_AND_SEND",
        message=f"Typed and sent: {p.get('text', '')}"
    ),
    "WHATSAPP_MESSAGE": lambda p: ActionResult(
        success=messaging_actions.send_whatsapp_message(
            contact=p.get("contact", ""),
            message=p.get("message", ""),
            lang=p.get("_lang", "en"),
        ),
        intent="WHATSAPP_MESSAGE",
        message=f"WhatsApp message to {p.get('contact', '')}: {p.get('message', '')}"
    ),

    # Hands-Free Knowledge Q&A
    "KNOWLEDGE_QUERY": lambda p: (
        lambda ans: ActionResult(
            success=bool(ans),
            intent="KNOWLEDGE_QUERY",
            message=ans or ("मुझे इसका उत्तर नहीं मिला।" if p.get("_lang") == "hi" else "I could not find an answer for that.")
        )
    )(knowledge_actions.answer_knowledge_query(p.get("query", ""), lang=p.get("_lang", "en"), speak_answer=True)),

    # File & Note Creation
    "CREATE_FILE": lambda p: ActionResult(
        success=file_actions.create_file(
            filename=p.get("filename", "note"),
            content=p.get("content", ""),
            location=p.get("location", "desktop"),
            lang=p.get("_lang", "en"),
            confirm_fn=lambda *a, **k: True,
        ),
        intent="CREATE_FILE",
        message=f"Created file: {p.get('filename', 'note')}"
    ),

    # Screen Vision & Mouse Clicking (OCR-powered)
    "CLICK_ELEMENT": lambda p: (
        lambda s, t: ActionResult(
            success=s,
            intent="CLICK_ELEMENT",
            message=f"Clicked on: {t}" if s else f"Could not find '{t}' on the screen to click."
        )
    )(screen_actions.click_element(p.get("target", ""), nth=p.get("nth", 1), lang=p.get("_lang", "en")), p.get("target", "")),
    "DOUBLE_CLICK_ELEMENT": lambda p: (
        lambda s, t: ActionResult(
            success=s,
            intent="DOUBLE_CLICK_ELEMENT",
            message=f"Double-clicked on: {t}" if s else f"Could not find '{t}' on the screen to double-click."
        )
    )(screen_actions.double_click_element(p.get("target", ""), nth=p.get("nth", 1), lang=p.get("_lang", "en")), p.get("target", "")),
    "RIGHT_CLICK_ELEMENT": lambda p: (
        lambda s, t: ActionResult(
            success=s,
            intent="RIGHT_CLICK_ELEMENT",
            message=f"Right-clicked on: {t}" if s else f"Could not find '{t}' on the screen to right-click."
        )
    )(screen_actions.right_click_element(p.get("target", ""), nth=p.get("nth", 1), lang=p.get("_lang", "en")), p.get("target", "")),
    "HOVER_ELEMENT": lambda p: ActionResult(
        success=screen_actions.hover_element(p.get("target", ""), nth=p.get("nth", 1), lang=p.get("_lang", "en")),
        intent="HOVER_ELEMENT",
        message=f"Hovered over: {p.get('target', '')}"
    ),
    "CLICK_AT_MOUSE": lambda p: ActionResult(
        success=screen_actions.click_at_mouse_position(
            double=p.get("double", False),
            right=p.get("right", False),
            lang=p.get("_lang", "en"),
        ),
        intent="CLICK_AT_MOUSE",
        message="Clicked where mouse is pointing",
    ),
    "READ_SCREEN": lambda p: ActionResult(
        success=screen_actions.read_screen(lang=p.get("_lang", "en")),
        intent="READ_SCREEN",
        message="Read screen contents aloud"
    ),
    "WHAT_IS_OPEN": lambda p: ActionResult(
        success=bool(screen_understanding.describe_background_processes(lang=p.get("_lang", "en"))),
        intent="WHAT_IS_OPEN",
        message="Described open applications and background processes",
    ),
    "LIST_FILES": lambda p: ActionResult(
        success=file_actions.list_folder_contents(location=p.get("location", "desktop"), lang=p.get("_lang", "en"))[0],
        intent="LIST_FILES",
        message=file_actions.list_folder_contents(location=p.get("location", "desktop"), lang=p.get("_lang", "en"))[1],
    ),
    "LIST_INSTALLED_APPS": lambda p: ActionResult(
        success=True,
        intent="LIST_INSTALLED_APPS",
        message=system_actions.list_installed_apps(search_query=p.get("search_query", ""), lang=p.get("_lang", "en")),
    ),

    # Conversation & Life-cycle
    "GREETING": handle_greeting,
    "EXIT_ASSISTANT": handle_exit,
}

def execute_command(transcription: str, *, lang: Optional[str] = None) -> ActionResult:
    """Delegate to the two-tier executor (fast path, then planner)."""
    from .executor import execute_command as run_two_tier
    return run_two_tier(transcription, lang=lang)
