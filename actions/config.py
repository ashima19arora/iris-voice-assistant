"""
Central allowlists for Iris. Extend sites, apps, and safe folders here.
"""
import os
from pathlib import Path

# --- Two-tier routing (executor.py). Do not hardcode 0.6 elsewhere. ---
# Override with IRIS_FAST_PATH_MIN_CONFIDENCE. Default 0.6: regex matches
# below this (including the generic "open X" fallback at ~0.55) go to Tier 2.
FAST_PATH_MIN_CONFIDENCE = float(os.getenv("IRIS_FAST_PATH_MIN_CONFIDENCE", "0.6"))
# Intents that always use the planner even at high regex confidence (LLM cost).
TIER2_ALWAYS_INTENTS = frozenset({"KNOWLEDGE_QUERY"})

OPENROUTER_PLANNER_MODEL = os.getenv("OPENROUTER_PLANNER_MODEL", "openai/gpt-4o-mini")
PLANNER_TIMEOUT_SEC = float(os.getenv("IRIS_PLANNER_TIMEOUT_SEC", "8"))
MAX_PLANNER_TOOL_CALLS = int(os.getenv("IRIS_MAX_PLANNER_TOOL_CALLS", "5"))
CONFIRMATION_TIMEOUT_SEC = float(os.getenv("IRIS_CONFIRMATION_TIMEOUT_SEC", "8"))
CONTEXT_TIMEOUT_SEC = float(os.getenv("IRIS_CONTEXT_TIMEOUT_SEC", "2.0"))

ALLOWED_URL_SCHEMES = ("http", "https")

SITE_NAME_MAP = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "github": "https://www.github.com",
    "gmail": "https://mail.google.com",
    "reddit": "https://www.reddit.com",
    "wikipedia": "https://www.wikipedia.org",
    "twitter": "https://www.x.com",
    "x": "https://www.x.com",
    "linkedin": "https://www.linkedin.com",
    "chatgpt": "https://chatgpt.com",
    "netflix": "https://www.netflix.com",
    "amazon": "https://www.amazon.com",
    "maps": "https://maps.google.com",
    "news": "https://news.google.com",
    "whatsapp": "https://web.whatsapp.com",
    "whatsapp web": "https://web.whatsapp.com",
    "gov.in": "https://www.india.gov.in",
    "india.gov.in": "https://www.india.gov.in",
    "india government": "https://www.india.gov.in",
    "aarogya setu": "https://www.aarogyasetu.gov.in",
    "arogya setu": "https://www.aarogyasetu.gov.in",
    "aarogyasetu": "https://www.aarogyasetu.gov.in",
}

APPROVED_APPLICATIONS = {
    "notepad": "notepad.exe",
    "the notepad": "notepad.exe",
    "calculator": "calc.exe",
    "the calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "the paint": "mspaint.exe",
    "mspaint": "mspaint.exe",
    "explorer": "explorer.exe",
    "the explorer": "explorer.exe",
    "files": "explorer.exe",
    "file explorer": "explorer.exe",
    "the file explorer": "explorer.exe",
    "settings": "ms-settings:",
    "the settings": "ms-settings:",
    "setting": "ms-settings:",
    "windows settings": "ms-settings:",
    "control panel": "control.exe",
    "the control panel": "control.exe",
    "task manager": "taskmgr.exe",
    "the task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "windows task manager": "taskmgr.exe",
    "terminal": "wt.exe",
    "the terminal": "wt.exe",
    "windows terminal": "wt.exe",
    "whatsapp": "whatsapp:",
    "the whatsapp": "whatsapp:",
    "chrome": "chrome.exe",
    "the chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "the google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "the edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "the microsoft edge": "msedge.exe",
    "firefox": "firefox.exe",
    "the firefox": "firefox.exe",
    "spotify": "spotify.exe",
    "the spotify": "spotify.exe",
    "word": "winword.exe",
    "microsoft word": "winword.exe",
    "excel": "excel.exe",
    "microsoft excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "microsoft powerpoint": "powerpnt.exe",
    "visual studio code": "code.exe",
    "the visual studio code": "code.exe",
    "vscode": "code.exe",
    "vs code": "code.exe",
    "code": "code.exe",
    "cursor": "cursor.exe",
    "the cursor": "cursor.exe",
    "camera": "microsoft.windows.camera:",
}

ALLOWED_FILE_EXTENSIONS = {".txt", ".note", ".md", ".log"}
FORBIDDEN_FILE_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".ps1", ".vbs", ".msi", ".scr",
    ".jar", ".iso", ".dll", ".reg", ".com", ".pif", ".hta", ".py", ".sh",
}


def _existing(*candidates: Path) -> list:
    found = []
    for path in candidates:
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            continue
        if resolved.exists() and resolved not in found:
            found.append(resolved)
    return found


def safe_directories() -> dict:
    """Whitelisted write locations: Desktop, Documents, Iris folder."""
    home = Path.home()
    iris_dir = home / "Iris"
    onedrive_desktop = home / "OneDrive" / "Desktop"
    local_desktop = home / "Desktop"
    desktop_candidates = [onedrive_desktop, local_desktop] if onedrive_desktop.exists() else [local_desktop, onedrive_desktop]

    onedrive_docs = home / "OneDrive" / "Documents"
    local_docs = home / "Documents"
    docs_candidates = [onedrive_docs, local_docs] if onedrive_docs.exists() else [local_docs, onedrive_docs]

    mapping = {
        "desktop": _existing(*desktop_candidates),
        "documents": _existing(*docs_candidates),
        "iris": _existing(iris_dir) or [iris_dir],
    }
    return mapping


def default_desktop() -> Path:
    dirs = safe_directories()["desktop"]
    return dirs[0] if dirs else (Path.home() / "Desktop")
