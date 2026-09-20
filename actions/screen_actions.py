"""
Iris Screen Vision & Mouse Automation Module
==============================================
WHAT THIS FILE DOES (Simple English):
  This module gives Iris the ability to SEE what's on screen and CLICK on things.
  When you say "click on Home" or "click the first result", it:
    1. Takes a screenshot of your entire screen
    2. Runs OCR (Optical Character Recognition) to find all visible text and positions
    3. Fuzzy-matches your spoken target against detected text elements
    4. Moves the mouse to the matched element and clicks it

GREAT TECH & PACKAGES USED IN THIS FILE:
  - rapidocr_onnxruntime:
      * What it does: Pure Python OCR engine using ONNX Runtime for text detection.
      * Why we use it: No external binary (like Tesseract) needed. Reuses the same
        ONNX Runtime already installed for Parakeet ASR. Fast and accurate.
  - pyautogui:
      * What it does: Cross-platform mouse and keyboard automation.
      * Why we use it: Moves the mouse cursor to exact pixel coordinates and clicks,
        double-clicks, or right-clicks on detected elements.
  - difflib (SequenceMatcher):
      * What it does: Fuzzy string matching.
      * Why we use it: When the user says "click on Home" and OCR detects
        "Home - Unique Identification Authority", fuzzy matching finds the best
        substring match so approximate voice commands still work.
"""

import time
import re
from typing import Optional, List, Tuple, Dict, Any
from difflib import SequenceMatcher
import pyautogui
from PIL import Image
from .feedback import speak, notify

# Disable fail-safe for automated mouse movement
pyautogui.FAILSAFE = False

# Lazy-load OCR engine (only when first needed)
_ocr_engine = None
_ocr_available = None


def _get_ocr_engine():
    """Lazily initializes the RapidOCR engine on first use."""
    global _ocr_engine, _ocr_available
    if _ocr_available is not None:
        return _ocr_engine if _ocr_available else None

    try:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
        _ocr_available = True
        return _ocr_engine
    except ImportError:
        _ocr_available = False
        print("[Iris Screen] rapidocr-onnxruntime not installed. Run: pip install rapidocr-onnxruntime")
        return None
    except Exception as e:
        _ocr_available = False
        print(f"[Iris Screen] OCR initialization error: {e}")
        return None


def capture_screen() -> Optional[Image.Image]:
    """Captures a screenshot of the entire screen and returns it as a PIL Image."""
    try:
        screenshot = pyautogui.screenshot()
        return screenshot
    except Exception as e:
        print(f"[Iris Screen] Screenshot error: {e}")
        return None


def ocr_screen(image: Image.Image) -> List[Dict[str, Any]]:
    """
    Runs OCR on a PIL Image and returns detected text elements with bounding boxes.

    Returns a list of dicts: [{"text": str, "bbox": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]], "confidence": float}]
    The bbox is a list of 4 corner points of the text bounding box.
    """
    engine = _get_ocr_engine()
    if engine is None:
        return []

    try:
        import numpy as np
        img_array = np.array(image)
        result, elapse = engine(img_array)

        if result is None:
            return []

        elements = []
        for item in result:
            # RapidOCR returns: (bbox_points, text, confidence)
            bbox_points, text, confidence = item
            if text and text.strip():
                elements.append({
                    "text": text.strip(),
                    "bbox": bbox_points,
                    "confidence": confidence
                })

        return elements
    except Exception as e:
        print(f"[Iris Screen] OCR processing error: {e}")
        return []


def _bbox_center(bbox) -> Tuple[int, int]:
    """Calculates the center (x, y) pixel coordinates from a bounding box."""
    # bbox is [[x1,y1], [x2,y2], [x3,y3], [x4,y4]] — 4 corner points
    xs = [pt[0] for pt in bbox]
    ys = [pt[1] for pt in bbox]
    center_x = int(sum(xs) / len(xs))
    center_y = int(sum(ys) / len(ys))
    return (center_x, center_y)


def _fuzzy_score(target: str, candidate: str) -> float:
    """
    Returns a fuzzy match score (0.0 to 1.0) between target and candidate text.
    Handles exact, compact alphanumeric, substring, and sequence matching.
    """
    target_lower = target.lower().strip()
    candidate_lower = candidate.lower().strip()

    # Exact match
    if target_lower == candidate_lower:
        return 1.0

    # Compact alphanumeric match (e.g. "aarogya setu" vs "AarogyaSetu 2.0")
    t_compact = re.sub(r'[^a-z0-9]', '', target_lower)
    c_compact = re.sub(r'[^a-z0-9]', '', candidate_lower)
    if t_compact and c_compact:
        if t_compact == c_compact:
            return 0.98
        if t_compact in c_compact:
            return 0.95

    # Exact substring match (e.g., "Home" in "Home - UIDAI")
    if target_lower in candidate_lower:
        return 0.90 + (0.08 * len(target_lower) / max(len(candidate_lower), 1))

    # Word-level match: target word is a whole word in candidate
    words = candidate_lower.split()
    if target_lower in words:
        return 0.85

    # Word set overlap (e.g. target="google aid", candidate="google play")
    target_words = set(target_lower.split())
    cand_words = set(words)
    common_words = target_words.intersection(cand_words)
    if common_words:
        overlap_ratio = len(common_words) / max(len(target_words), 1)
        if overlap_ratio >= 0.5:
            return 0.70 + (0.20 * overlap_ratio)

    # Fuzzy sequence matching
    return SequenceMatcher(None, target_lower, candidate_lower).ratio()


def find_element_via_uia(target_text: str, nth: int = 1) -> Optional[Tuple[int, int]]:
    """
    Attempts to find a native Windows UI control matching target_text using uiautomation.
    Returns (x, y) center coordinates or None if not found or uiautomation is unavailable.
    """
    try:
        import uiautomation as auto
        focused = auto.GetFocusedControl()
        if not focused:
            return None
        top_window = focused.GetTopLevelControl()
        if not top_window:
            return None

        target_l = target_text.lower().strip()
        matches = []

        for ctrl, depth in auto.WalkTree(top_window, getChildren=lambda c: c.GetChildren()):
            if ctrl.IsOffscreen:
                continue
            name = (ctrl.Name or "").strip()
            if not name:
                continue
            rect = ctrl.BoundingRectangle
            if rect.width() <= 0 or rect.height() <= 0:
                continue

            score = _fuzzy_score(target_l, name)
            if score >= 0.75:
                cx = rect.left + rect.width() // 2
                cy = rect.top + rect.height() // 2
                matches.append({"name": name, "score": score, "center": (cx, cy), "y": cy})

        if matches:
            matches.sort(key=lambda m: (-m["score"], m["y"]))
            idx = min(nth - 1, len(matches) - 1)
            return matches[idx]["center"]
    except Exception as exc:
        pass
    return None


def click_at_mouse_position(double: bool = False, right: bool = False, lang: str = "en") -> bool:
    """Directly clicks the current mouse pointer position without OCR."""
    x, y = pyautogui.position()
    notify(f"Clicking at mouse position ({x}, {y})")
    print(f"\033[95m[Iris Mouse]\033[0m Clicking current cursor position at ({x}, {y})", flush=True)
    if double:
        pyautogui.doubleClick(x, y)
        speak("Double clicked where mouse is pointing." if lang != "hi" else "माउस पर डबल क्लिक कर दिया।", lang=lang)
    elif right:
        pyautogui.rightClick(x, y)
        speak("Right clicked where mouse is pointing." if lang != "hi" else "माउस पर राइट क्लिक कर दिया।", lang=lang)
    else:
        pyautogui.click(x, y)
        speak("Clicked where mouse is pointing." if lang != "hi" else "माउस पर क्लिक कर दिया।", lang=lang)
    return True


def find_element_by_text(
    target: str,
    ocr_results: List[Dict[str, Any]],
    nth: int = 1,
    min_confidence: float = 0.4
) -> Optional[Dict[str, Any]]:
    """
    Finds the best matching OCR element for the given target text with layout awareness.
    """
    if not target or not ocr_results:
        return None

    target_lower = target.lower().strip()
    # Pronoun safety guard: reject matching bare pronouns against random screen buttons
    if target_lower in ("that", "this", "it", "there"):
        return None

    is_generic_result = target_lower in (
        "link", "result", "search result", "the link", "displayed link",
        "link that is being displayed", "the google link", "first link", "first result"
    )

    if is_generic_result and ocr_results:
        content_candidates = []
        for elem in ocr_results:
            center = _bbox_center(elem["bbox"])
            text = elem["text"].strip()
            text_l = text.lower()

            # Exclude header & search input bar (y < 230)
            if center[1] < 230:
                continue
            # Exclude far-right sidebar (Copilot/chat at x > 1400 on wide screens)
            if center[0] > 1400:
                continue
            # Exclude search category tabs and navigation noise
            if text_l in (
                "google", "all", "images", "videos", "news", "maps", "tools", "more",
                "sign in", "search", "ai mode", "forums", "shopping", "short videos",
                "people also ask", "did you mean", "search instead for", "filters"
            ):
                continue
            if len(text) < 5:
                continue

            priority_score = 0.90
            if any(k in text_l for k in ("http", "www.", ".com", ".org", ".gov", "youtube", "play.google", "songs", "video", ">")):
                priority_score = 0.95

            content_candidates.append({
                **elem,
                "match_score": priority_score,
                "center": center,
            })
        if content_candidates:
            # Sort top-to-bottom by reading order
            content_candidates.sort(key=lambda e: (e["center"][1], e["center"][0]))
            idx = min(nth - 1, len(content_candidates) - 1)
            return content_candidates[idx]

    # Score all elements
    scored = []
    for elem in ocr_results:
        center = _bbox_center(elem["bbox"])
        # Exclude far-right sidebar unless user specifically requested chat/copilot
        if center[0] > 1400 and not any(w in target_lower for w in ("chat", "copilot", "sidebar", "right")):
            continue

        score = _fuzzy_score(target, elem["text"])
        if score >= min_confidence:
            scored.append({
                **elem,
                "match_score": score,
                "center": center
            })

    if not scored:
        return None

    # Sort by match score (descending), then by reading order (top-to-bottom)
    scored.sort(key=lambda e: (-e["match_score"], e["center"][1], e["center"][0]))
    idx = min(nth - 1, len(scored) - 1)
    return scored[idx]


def click_element(target_text: str, nth: int = 1, lang: str = 'en') -> bool:
    """
    Full pipeline: check mouse pointer -> native UIA -> screenshot OCR -> click.
    """
    if not target_text:
        speak("I need to know what to click on. Please say click on and the name of the element.", lang=lang)
        return False

    clean_target = target_text.lower().strip()
    if clean_target in (
        "where the mouse is pointing", "where the mouse is", "where mouse is pointing",
        "where mouse is", "here", "cursor", "current position", "at cursor",
        "where the mouse is pointing currently", "where mouse is pointing currently"
    ):
        return click_at_mouse_position(lang=lang)

    if clean_target in ("that", "this", "it", "there"):
        speak("I am not sure what you want me to click on. Please say the name of the link or button.", lang=lang)
        return False

    is_generic_link = clean_target in (
        "link", "result", "search result", "first link", "first result",
        "link that is there", "first link that is there", "top link", "top result",
        "the link", "website link", "website", "url", "page link", "the first link"
    ) or bool(re.match(r"^(?:first|second|third|1st|2nd|3rd|top|next)?\s*(?:link|result|search\s+result|website)\b", clean_target))

    # Try native Windows UI Automation if target is specific
    if not is_generic_link:
        uia_coords = find_element_via_uia(target_text, nth=nth)
        if uia_coords:
            x, y = uia_coords
            notify(f"Found '{target_text}' via UIA at ({x}, {y}). Clicking...")
            print(f"\033[95m[Iris UIA]\033[0m Found '{target_text}' at ({x}, {y}) — clicking", flush=True)
            pyautogui.moveTo(x, y, duration=0.25)
            time.sleep(0.05)
            pyautogui.click(x, y)
            speak(f"Clicked on {target_text}" if lang != 'hi' else f"{target_text} पर क्लिक कर दिया", lang=lang)
            return True

    engine = _get_ocr_engine()
    if engine is None:
        speak("Screen vision is not available. Please install rapid O C R by running pip install rapidocr-onnxruntime.", lang=lang)
        return False

    notify(f"Looking for '{target_text}' on screen...")
    speak(f"Looking for {target_text}" if lang != 'hi' else f"{target_text} ढूंढ रहा हूँ", lang=lang)

    # Step 1: Capture screen
    screenshot = capture_screen()
    if screenshot is None:
        speak("Could not capture the screen." if lang != 'hi' else "स्क्रीन कैप्चर नहीं हो पाया।", lang=lang)
        return False

    # Step 2: OCR
    ocr_results = ocr_screen(screenshot)
    if not ocr_results:
        speak("I couldn't read anything on the screen." if lang != 'hi' else "स्क्रीन पर कुछ नहीं पढ़ पाया।", lang=lang)
        return False

    # Step 3: Find element
    match = None
    if is_generic_link:
        # Collect candidate search results or primary links on screen
        candidates = []
        for elem in ocr_results:
            t = elem["text"].strip()
            c = _bbox_center(elem["bbox"])
            # Main content area: y >= 200, x < 1400, length >= 6
            if 200 <= c[1] <= 950 and 60 <= c[0] <= 1400:
                t_lower = t.lower()
                if len(t) >= 6 and not any(k in t_lower for k in (
                    "iris orb", "iris ai assistant", "people also ask", "did you mean",
                    "search instead", "filters", "all filters", "tools", "cached"
                )):
                    candidates.append({
                        "text": t,
                        "center": c,
                        "bbox": elem["bbox"],
                        "match_score": 1.0,
                    })
        # Sort candidates top-to-bottom
        candidates.sort(key=lambda e: (e["center"][1], e["center"][0]))
        if candidates:
            idx = min(max(0, nth - 1), len(candidates) - 1)
            match = candidates[idx]
    else:
        match = find_element_by_text(target_text, ocr_results, nth=nth)

    if match is None:
        speak(f"I couldn't find {target_text} on the screen. Try saying it differently." if lang != 'hi'
              else f"स्क्रीन पर {target_text} नहीं मिला।", lang=lang)
        return False

    # Step 4: Click
    x, y = match["center"]
    matched_text = match["text"]
    score = match["match_score"]

    notify(f"Found '{matched_text}' (score: {score:.2f}) at ({x}, {y}). Clicking...")
    print(f"\033[95m[Iris Vision]\033[0m Found '{matched_text}' at ({x}, {y}) — clicking", flush=True)

    pyautogui.moveTo(x, y, duration=0.3)
    time.sleep(0.1)
    pyautogui.click(x, y)

    speak(f"Clicked on {matched_text}" if lang != 'hi' else f"{matched_text} पर क्लिक कर दिया", lang=lang)
    return True


def double_click_element(target_text: str, nth: int = 1, lang: str = 'en') -> bool:
    """Full pipeline: screenshot → OCR → find target → double-click."""
    if not target_text:
        return False

    engine = _get_ocr_engine()
    if engine is None:
        speak("Screen vision is not available.", lang=lang)
        return False

    notify(f"Double-clicking '{target_text}'...")

    screenshot = capture_screen()
    if screenshot is None:
        return False

    ocr_results = ocr_screen(screenshot)
    match = find_element_by_text(target_text, ocr_results, nth=nth)
    if match is None:
        speak(f"I couldn't find {target_text} on the screen." if lang != 'hi'
              else f"स्क्रीन पर {target_text} नहीं मिला।", lang=lang)
        return False

    x, y = match["center"]
    print(f"\033[95m[Iris Vision]\033[0m Double-clicking '{match['text']}' at ({x}, {y})", flush=True)

    pyautogui.moveTo(x, y, duration=0.3)
    time.sleep(0.1)
    pyautogui.doubleClick(x, y)

    speak(f"Double clicked on {target_text}" if lang != 'hi'
          else f"{target_text} पर डबल क्लिक कर दिया", lang=lang)
    return True


def right_click_element(target_text: str, nth: int = 1, lang: str = 'en') -> bool:
    """Full pipeline: screenshot → OCR → find target → right-click."""
    if not target_text:
        return False

    engine = _get_ocr_engine()
    if engine is None:
        speak("Screen vision is not available.", lang=lang)
        return False

    notify(f"Right-clicking '{target_text}'...")

    screenshot = capture_screen()
    if screenshot is None:
        return False

    ocr_results = ocr_screen(screenshot)
    match = find_element_by_text(target_text, ocr_results, nth=nth)
    if match is None:
        speak(f"I couldn't find {target_text} on the screen." if lang != 'hi'
              else f"स्क्रीन पर {target_text} नहीं मिला।", lang=lang)
        return False

    x, y = match["center"]
    print(f"\033[95m[Iris Vision]\033[0m Right-clicking '{match['text']}' at ({x}, {y})", flush=True)

    pyautogui.moveTo(x, y, duration=0.3)
    time.sleep(0.1)
    pyautogui.rightClick(x, y)

    speak(f"Right clicked on {target_text}" if lang != 'hi'
          else f"{target_text} पर राइट क्लिक कर दिया", lang=lang)
    return True


def hover_element(target_text: str, nth: int = 1, lang: str = 'en') -> bool:
    """Full pipeline: screenshot → OCR → find target → move mouse (no click)."""
    if not target_text:
        return False

    engine = _get_ocr_engine()
    if engine is None:
        speak("Screen vision is not available.", lang=lang)
        return False

    notify(f"Moving mouse to '{target_text}'...")

    screenshot = capture_screen()
    if screenshot is None:
        return False

    ocr_results = ocr_screen(screenshot)
    match = find_element_by_text(target_text, ocr_results, nth=nth)
    if match is None:
        speak(f"I couldn't find {target_text} on the screen." if lang != 'hi'
              else f"स्क्रीन पर {target_text} नहीं मिला।", lang=lang)
        return False

    x, y = match["center"]
    print(f"\033[95m[Iris Vision]\033[0m Hovering over '{match['text']}' at ({x}, {y})", flush=True)

    pyautogui.moveTo(x, y, duration=0.4)

    speak(f"Mouse is now on {target_text}" if lang != 'hi'
          else f"माउस {target_text} पर है", lang=lang)
    return True


def read_screen(lang: str = 'en') -> bool:
    """Takes a screenshot, analyzes active window & visible text, and speaks summary aloud."""
    try:
        from . import screen_understanding
        spoken = screen_understanding.describe_screen(lang=lang)
        if spoken and not spoken.startswith("I was unable"):
            return True
    except Exception:
        pass

    engine = _get_ocr_engine()
    if engine is None:
        speak("Screen vision is not available.", lang=lang)
        return False

    notify("Reading screen...")
    speak("Reading what's on screen" if lang != 'hi' else "स्क्रीन पढ़ रहा हूँ", lang=lang)

    screenshot = capture_screen()
    if screenshot is None:
        return False

    ocr_results = ocr_screen(screenshot)
    if not ocr_results:
        speak("I couldn't read anything on the screen." if lang != 'hi'
              else "स्क्रीन पर कुछ नहीं पढ़ पाया।", lang=lang)
        return False

    # Sort by reading order (top-to-bottom, left-to-right)
    sorted_results = sorted(ocr_results, key=lambda e: (_bbox_center(e["bbox"])[1], _bbox_center(e["bbox"])[0]))

    # Combine all text, deduplicating adjacent identical texts
    all_text = []
    prev = ""
    for elem in sorted_results:
        text = elem["text"].strip()
        if text and text != prev:
            all_text.append(text)
            prev = text

    # Limit to first ~500 chars for reasonable spoken output
    combined = ". ".join(all_text)
    if len(combined) > 500:
        combined = combined[:500] + "... and more."

    print(f"\033[95m[Iris Vision]\033[0m Read {len(all_text)} text elements from screen", flush=True)
    speak(combined, lang=lang)
    return True
