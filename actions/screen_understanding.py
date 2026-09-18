"""
Iris Screen Scene & Background Understanding Module
===================================================
Provides environmental awareness for Iris:
  1. Identifies the active/focused application window.
  2. Lists running user applications in the background (Edge, Chrome, VS Code, etc.).
  3. Analyzes on-screen layout (search results, tabs, active documents).
  4. Synthesizes natural spoken summaries for:
     - "What is on my screen?"
     - "What is open right now?"
     - "What is running in the background?"
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional

from .feedback import speak, notify

logger = logging.getLogger("iris")

# Common friendly application process mappings
FRIENDLY_APP_NAMES = {
    "msedge.exe": "Microsoft Edge",
    "chrome.exe": "Google Chrome",
    "firefox.exe": "Firefox",
    "brave.exe": "Brave Browser",
    "code.exe": "Visual Studio Code",
    "cursor.exe": "Cursor",
    "notepad.exe": "Notepad",
    "explorer.exe": "File Explorer",
    "spotify.exe": "Spotify",
    "windowsterminal.exe": "Windows Terminal",
    "wt.exe": "Windows Terminal",
    "cmd.exe": "Command Prompt",
    "powershell.exe": "PowerShell",
    "calc.exe": "Calculator",
    "mspaint.exe": "Paint",
    "taskmgr.exe": "Task Manager",
    "slack.exe": "Slack",
    "discord.exe": "Discord",
    "teams.exe": "Microsoft Teams",
    "winword.exe": "Microsoft Word",
    "excel.exe": "Microsoft Excel",
    "powerpnt.exe": "Microsoft PowerPoint",
    "whatsapp.exe": "WhatsApp",
}

# System processes to ignore when listing user apps
SYSTEM_PROCESS_IGNORE = {
    "system", "registry", "smss.exe", "csrss.exe", "wininit.exe", "services.exe",
    "lsass.exe", "svchost.exe", "fontdrvhost.exe", "dwm.exe", "spoolsv.exe",
    "sihost.exe", "taskhostw.exe", "ctfmon.exe", "searchhost.exe", "shellexperiencehost.exe",
    "startmenuexperiencehost.exe", "runtimebroker.exe", "applicationframehost.exe",
    "conhost.exe", "wlanext.exe", "smartscreen.exe", "securityhealthservice.exe",
    "audiodg.exe", "igfxcuiservice.exe", "oneapp.igcc.winservice.exe",
}


def get_active_window_info() -> Dict[str, Any]:
    """
    Returns information about the current foreground/active window:
    {'title': str, 'app_name': str, 'process_name': str, 'rect': (left, top, right, bottom)}
    """
    info = {"title": "", "app_name": "", "process_name": "", "rect": (0, 0, 0, 0)}
    try:
        import win32gui
        import win32process
        import psutil

        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            title = win32gui.GetWindowText(hwnd).strip()
            info["title"] = title
            try:
                rect = win32gui.GetWindowRect(hwnd)
                info["rect"] = rect
            except Exception:
                pass

            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid > 0:
                    proc = psutil.Process(pid)
                    proc_name = proc.name().lower()
                    info["process_name"] = proc_name
                    info["app_name"] = FRIENDLY_APP_NAMES.get(proc_name, proc_name.replace(".exe", "").title())
            except Exception:
                pass
    except Exception as exc:
        logger.debug("win32 active window lookup failed: %s", exc)

    # Fallback to uiautomation if available and win32 didn't find title
    if not info["title"]:
        try:
            import uiautomation as auto
            focused = auto.GetFocusedControl()
            if focused:
                top_level = focused.GetTopLevelControl()
                if top_level and top_level.Name:
                    info["title"] = top_level.Name.strip()
                    if not info["app_name"]:
                        info["app_name"] = top_level.Name.split(" - ")[-1].strip()
        except Exception:
            pass

    return info


def get_background_apps(limit: int = 8) -> List[Dict[str, str]]:
    """
    Returns a list of active user-facing applications running on the system:
    [{'name': 'Microsoft Edge', 'process': 'msedge.exe', 'pid': 1234}, ...]
    """
    apps = []
    seen = set()

    try:
        import psutil
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pname = (proc.info.get("name") or "").lower()
                if not pname or pname in SYSTEM_PROCESS_IGNORE:
                    continue
                if pname in FRIENDLY_APP_NAMES:
                    friendly = FRIENDLY_APP_NAMES[pname]
                    if friendly not in seen:
                        seen.add(friendly)
                        apps.append({
                            "name": friendly,
                            "process": pname,
                            "pid": proc.info.get("pid"),
                        })
                        if len(apps) >= limit:
                            break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as exc:
        logger.warning("get_background_apps error: %s", exc)

    return apps


def analyze_screen_content() -> Dict[str, Any]:
    """
    Captures the screen and extracts high-level semantic content:
    - active window / page type (e.g. Google Search, YouTube, Editor)
    - search query if present
    - search results if present
    - main text highlights
    """
    from .screen_actions import capture_screen, ocr_screen, _bbox_center

    active_win = get_active_window_info()
    screenshot = capture_screen()
    if screenshot is None:
        return {"ok": False, "error": "Could not capture screen", "active_window": active_win}

    ocr_elements = ocr_screen(screenshot)
    if not ocr_elements:
        return {"ok": True, "active_window": active_win, "search_results": [], "summary": "Screen contains no readable text."}

    # Sort top-to-bottom
    sorted_elements = sorted(ocr_elements, key=lambda e: (_bbox_center(e["bbox"])[1], _bbox_center(e["bbox"])[0]))

    search_query = ""
    search_results = []
    other_highlights = []

    # Detect if search engine is active
    for elem in sorted_elements:
        text = elem["text"].strip()
        center = _bbox_center(elem["bbox"])
        # Query box often around y=90..180
        if not search_query and 80 < center[1] < 190 and len(text) > 4:
            if not any(k in text.lower() for k in ("google", "http", "search", "youtube", "chat")):
                search_query = text

        # Results area: y >= 230 and x < 1400 (avoiding sidebar Copilot)
        if 230 <= center[1] <= 900 and center[0] < 1400:
            # Check for result-like titles
            if len(text) >= 8 and not any(k in text.lower() for k in (
                "people also ask", "did you mean", "search instead", "filters", "videos", "images", "news", "tools"
            )):
                search_results.append({
                    "text": text,
                    "center": center,
                    "y": center[1],
                })
        elif center[1] > 190 and len(text) >= 12:
            other_highlights.append(text)

    return {
        "ok": True,
        "active_window": active_win,
        "search_query": search_query,
        "search_results": [r["text"] for r in search_results[:5]],
        "highlights": other_highlights[:5],
    }


def describe_screen(lang: str = "en", speak_aloud: bool = True) -> str:
    """
    Produces a crisp, punchy 1-liner summary of what is on screen, and optionally speaks it aloud.
    """
    notify("Analyzing screen...")
    analysis = analyze_screen_content()
    if not analysis.get("ok"):
        msg = "I cannot read the screen right now." if lang != "hi" else "स्क्रीन नहीं पढ़ पा रहा हूँ।"
        if speak_aloud:
            speak(msg, lang=lang)
        return msg

    win = analysis.get("active_window", {})
    win_title = win.get("title") or ""
    app_name = win.get("app_name") or ""
    query = analysis.get("search_query")

    # Clean up window title to avoid raw symbols or long paths
    clean_title = win_title
    if " - " in clean_title:
        parts = [p.strip() for p in clean_title.split(" - ") if p.strip()]
        if len(parts) >= 2:
            clean_title = f"{parts[-2]} with {parts[-1]}"

    # Formulate a crisp 1-liner
    if any(k in app_name.lower() for k in ("edge", "chrome", "firefox", "browser")):
        if query and any(q_word in win_title.lower() for q_word in ("search", "google", "bing")):
            spoken = f"You are on Google Search for {query} in {app_name}."
        elif "youtube" in win_title.lower():
            spoken = f"You are on YouTube in {app_name}."
        elif clean_title:
            spoken = f"You are on {clean_title}."
        else:
            spoken = f"You are on {app_name}."
    elif clean_title:
        spoken = f"You are on {clean_title}."
    elif app_name:
        spoken = f"You are on {app_name}."
    else:
        spoken = "Your desktop is currently open." if lang != "hi" else "आपका डेस्कटॉप खुला हुआ है।"

    logger.info("Screen description: %s", spoken)
    if speak_aloud:
        speak(spoken, lang=lang)
    return spoken


def describe_background_processes(lang: str = "en", speak_aloud: bool = True) -> str:
    """
    Produces a concise 1-liner summary of active applications running in background.
    """
    notify("Checking open applications...")
    bg_apps = get_background_apps(limit=4)
    app_names = [a["name"] for a in bg_apps]

    if not app_names:
        spoken = "No major apps running in background." if lang != "hi" else "कोई ऐप बैकग्राउंड में नहीं चल रहा।"
    else:
        spoken = f"Running apps: {', '.join(app_names[:3])}."

    logger.info("Background processes: %s", spoken)
    if speak_aloud:
        speak(spoken, lang=lang)
    return spoken
