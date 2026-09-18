"""Live context for the Tier-2 planner: optional screen folder listing (os.scandir)."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from .config import CONTEXT_TIMEOUT_SEC, safe_directories
from .feedback import speak

logger = logging.getLogger("iris")


def fs_list_directory(location: str = "desktop", limit: int = 40) -> Dict[str, Any]:
    """List an allowlisted folder using os.scandir only."""
    loc = (location or "desktop").lower().strip()
    if loc in ("docs", "doc"):
        loc = "documents"
    roots = safe_directories().get(loc)
    if not roots:
        logger.warning("validation rejection: unknown folder alias %r", location)
        return {"ok": False, "error": f"Unknown folder '{location}'.", "entries": [], "path": ""}
    root: Path = roots[0]
    if not root.exists():
        logger.warning("context: folder missing %s", root)
        return {"ok": False, "error": f"Folder does not exist: {root}", "entries": [], "path": str(root)}
    entries: List[str] = []
    with os.scandir(root) as it:
        for i, item in enumerate(it):
            if i >= limit:
                break
            mark = "/" if item.is_dir(follow_symlinks=False) else ""
            entries.append(item.name + mark)
    return {"ok": True, "error": "", "entries": entries, "path": str(root)}


def gather_context(
    folder: str = "desktop",
    timeout: float = CONTEXT_TIMEOUT_SEC,
    lang: str = "en",
    utterance: str = "",
    include_folder: bool | None = None,
    include_browser: bool | None = None,
    speak_errors: bool = False,
) -> Dict[str, Any]:
    """
    Bounded context. Playwright is NOT used here (it is not thread-safe and is a
    separate browser, not the user's Chrome). Folder listing only when the user
    asked about files, so desktop .lnk names cannot poison app_launch.
    """
    text = (utterance or "").lower()
    if include_folder is None:
        include_folder = any(w in text for w in ("folder", "directory", "desktop files", "what's in", "what is in", "list files"))
    if include_browser is None:
        include_browser = False

    snapshot: Dict[str, Any] = {
        "browser": {"ok": False, "error": "Use click_on_screen / search_web for the user's Chrome.", "elements": [], "url": "", "title": ""},
        "folder": {"ok": False, "error": "", "entries": [], "path": ""},
        "spoken_fallback": "",
        "allowed_apps": [
            "notepad", "calculator", "paint", "explorer", "settings", "whatsapp",
            "chrome", "edge", "firefox", "spotify", "word", "excel", "powerpoint",
            "task manager",
        ],
    }

    if include_folder:
        try:
            snapshot["folder"] = fs_list_directory(folder)
            if not snapshot["folder"].get("ok"):
                snapshot["spoken_fallback"] = snapshot["folder"].get("error") or "I could not read that folder."
        except Exception as exc:
            logger.warning("folder context failed: %s", exc)
            snapshot["folder"]["error"] = str(exc)
            snapshot["spoken_fallback"] = "I could not read that folder."

    if include_browser:
        try:
            from . import browser_runtime
            snapshot["browser"] = browser_runtime.snapshot_elements()
        except Exception as exc:
            logger.warning("browser context failed: %s", exc)
            snapshot["browser"]["error"] = "No active automation browser."
            snapshot["spoken_fallback"] = snapshot["spoken_fallback"] or (
                "I don't have an automated browser window."
                if lang != "hi"
                else "कोई ब्राउज़र विंडो नहीं है।"
            )

    if speak_errors and snapshot["spoken_fallback"]:
        speak(snapshot["spoken_fallback"], lang=lang)
    return snapshot
