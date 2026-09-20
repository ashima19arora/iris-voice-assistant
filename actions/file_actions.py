"""Iris File Actions — whitelist writes; reject traversal; confirm before write."""
import logging
import os
import re
from pathlib import Path
from typing import Callable, Optional, Tuple

from .config import ALLOWED_FILE_EXTENSIONS, FORBIDDEN_FILE_EXTENSIONS, safe_directories
from .confirmation import request_confirmation
from .feedback import speak, notify

logger = logging.getLogger("iris")


class UnsafeFileName(ValueError):
    pass


def get_target_directory(location: str = "desktop") -> str:
    clean_loc = (location or "desktop").lower().strip()
    if clean_loc in ("docs", "doc"):
        clean_loc = "documents"
    if clean_loc not in ("desktop", "documents", "iris"):
        raise UnsafeFileName(f"Location '{location}' is not an allowed folder.")
    dirs = safe_directories().get(clean_loc) or []
    if not dirs:
        raise UnsafeFileName("Allowed folder is missing on this computer.")
    target = dirs[0]
    target.mkdir(parents=True, exist_ok=True)
    return str(target)


def validate_file_name(raw_name: str) -> Tuple[bool, str, str]:
    clean = (raw_name or "").strip()
    if not clean:
        return False, "", "Empty filename."
    if "\x00" in clean:
        return False, "", "Filename contains a null byte."
    normalized = clean.replace("\\", "/")
    if ".." in normalized.split("/"):
        logger.warning("validation rejection: path traversal in filename %r", raw_name)
        return False, "", "Path traversal is not allowed."
    if os.path.isabs(clean) or normalized.startswith("/") or re.match(r"^[a-zA-Z]:/", normalized):
        logger.warning("validation rejection: absolute path filename %r", raw_name)
        return False, "", "Absolute paths are not allowed."
    if "/" in normalized:
        logger.warning("validation rejection: nested path filename %r", raw_name)
        return False, "", "Folder paths in filenames are not allowed."

    clean = re.sub(r"^(?:named|called)\s+", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r'[\\/:*?"<>|]+', "", clean).strip()
    if not clean:
        return False, "", "Filename is empty after removing illegal characters."

    base, ext = os.path.splitext(clean)
    ext_lower = ext.lower()
    if ext_lower in FORBIDDEN_FILE_EXTENSIONS:
        logger.warning("validation rejection: forbidden extension %s", ext_lower)
        return False, "", f"Extension {ext_lower} is not allowed."
    if not ext:
        clean = f"{clean}.txt"
        ext_lower = ".txt"
    if ext_lower not in ALLOWED_FILE_EXTENSIONS:
        logger.warning("validation rejection: extension %s not allowlisted", ext_lower)
        return False, "", f"Extension {ext_lower} is not allowed."
    if not base:
        return False, "", "Filename is empty."
    return True, clean, "ok"


def sanitize_file_name(raw_name: str) -> str:
    ok, name, reason = validate_file_name(raw_name)
    if not ok:
        raise UnsafeFileName(reason)
    return name


def _is_inside_whitelist(filepath: Path) -> bool:
    resolved = filepath.resolve()
    allowed = []
    for paths in safe_directories().values():
        allowed.extend(paths)
    for root in allowed:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def create_file(
    filename: str,
    content: str = "",
    location: str = "desktop",
    open_after: bool = True,
    lang: str = "en",
    confirm_fn: Optional[Callable[..., bool]] = None,
) -> bool:
    ok, safe_name, reason = validate_file_name(filename)
    if not ok:
        notify(f"Write blocked: {reason}", success=False)
        speak("I can't create that file." if lang != "hi" else "वह फाइल नहीं बना सकता।", lang=lang)
        return False

    try:
        target_dir = Path(get_target_directory(location))
    except UnsafeFileName as exc:
        speak("I can't write there." if lang != "hi" else "वहाँ फाइल नहीं बना सकता।", lang=lang)
        logger.warning("validation rejection: %s", exc)
        return False

    filepath = target_dir / safe_name
    if not _is_inside_whitelist(filepath):
        notify("Write blocked: path is outside the safe folder list.", success=False)
        speak("I can't write there." if lang != "hi" else "वहाँ फाइल नहीं बना सकता।", lang=lang)
        return False

    prompt = (
        f"Create {safe_name} on {location}? Say yes to continue."
        if lang != "hi"
        else f"{location} पर {safe_name} बनाऊँ?"
    )
    if confirm_fn is not None:
        if not confirm_fn(prompt, lang=lang):
            logger.info("file create cancelled before write")
            return False

    base, ext = os.path.splitext(safe_name)
    counter = 1
    while filepath.exists():
        filepath = target_dir / f"{base} ({counter}){ext}"
        counter += 1
        if not _is_inside_whitelist(filepath):
            speak("I can't write there.", lang=lang)
            return False

    try:
        with open(filepath, "w", encoding="utf-8") as handle:
            handle.write(content or "")
        loc_label = "Desktop" if "desktop" in (location or "").lower() else location.capitalize()
        notify(f"Created file '{filepath.name}' on {loc_label}")
        if lang == "hi":
            speak(f"{filepath.name} फाइल बना दी गई है।", lang=lang)
        else:
            speak(f"Created {filepath.name} on your {loc_label}.", lang=lang)
        if open_after and hasattr(os, "startfile"):
            try:
                os.startfile(str(filepath))
            except Exception:
                pass
        return True
    except Exception as exc:
        notify(f"Failed to create file: {exc}", success=False)
        speak("I could not create that file.", lang=lang)
        return False


def list_folder_contents(location: str = "desktop", lang: str = "en") -> Tuple[bool, str]:
    """
    Safely lists document files in an approved directory (Desktop, Documents, Iris)
    without path traversal.
    """
    clean_loc = (location or "desktop").lower().strip()
    if clean_loc in ("docs", "doc"):
        clean_loc = "documents"
    if clean_loc not in ("desktop", "documents", "iris"):
        msg = f"Location '{location}' is not an authorized folder for security reasons."
        notify(msg, success=False)
        speak(msg, lang=lang)
        return False, msg

    dirs = safe_directories().get(clean_loc) or []
    if not dirs:
        msg = f"Could not find the {clean_loc} folder on this computer."
        notify(msg, success=False)
        speak(msg, lang=lang)
        return False, msg

    target = dirs[0]
    try:
        entries = [
            f.name for f in target.iterdir()
            if f.is_file() and not f.name.startswith((".", "~$"))
        ]
        count = len(entries)
        loc_label = "Desktop" if clean_loc == "desktop" else clean_loc.capitalize()
        if count == 0:
            msg = f"Your {loc_label} folder is currently empty."
        else:
            top_files = entries[:6]
            files_str = ", ".join(top_files)
            if count > 6:
                msg = f"Your {loc_label} contains {count} files, including: {files_str}."
            else:
                msg = f"Your {loc_label} contains {count} files: {files_str}."

        notify(msg)
        speak(msg, lang=lang)
        return True, msg
    except Exception as exc:
        msg = f"Could not list files in {clean_loc}: {exc}"
        notify(msg, success=False)
        speak(msg, lang=lang)
        return False, msg
