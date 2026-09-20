"""
Iris Messaging Actions — WhatsApp Web & App Messaging Automation
================================================================
WHAT THIS FILE DOES (Simple English):
  When a user says "send hello to Mayank on WhatsApp", this module handles the
  entire multi-step flow: focuses the browser, searches for the contact,
  opens their chat, types the message, and presses Enter to send it.

GREAT TECH & PACKAGES USED IN THIS FILE:
  - pyautogui:
      * What it does: Cross-platform mouse and keyboard automation.
      * Why we use it: Automates the multi-step WhatsApp Web interaction
        (search, select contact, type message, press Enter) reliably.
  - pyperclip:
      * What it does: Cross-platform clipboard text copy/paste.
      * Why we use it: Clipboard injection (Ctrl+V) is faster and more reliable
        than keystroke-by-keystroke typing, and handles Unicode characters.
  - pygetwindow:
      * What it does: Cross-platform window finding and activation.
      * Why we use it: Detects whether the Iris overlay has focus and transfers
        focus to the correct browser window before typing.
"""

import time
import logging
import pyautogui
from .feedback import speak, notify

pyautogui.FAILSAFE = False
logger = logging.getLogger("iris")


# ──────────────────────────────────────────────────────────────
# FOCUS MANAGEMENT — Shared by all typing / keyboard actions
# ──────────────────────────────────────────────────────────────

def _is_iris_focused() -> bool:
    """Check whether the Iris Electron overlay currently has keyboard focus."""
    try:
        import pygetwindow as gw
        active = gw.getActiveWindow()
        if active is None:
            return False
        title = (active.title or "").lower()
        # The Iris Electron window has "iris" in title, or it's a small
        # frameless Electron window. Check for common indicators.
        if "iris" in title or title == "" or "electron" in title:
            return True
    except Exception:
        pass
    return False


def transfer_focus_to_target_window():
    """
    If the Iris overlay currently owns focus, Alt+Tab back to whatever
    the user was working with before they invoked Iris.

    Safe to call unconditionally — it's a no-op when focus is already
    on the target application.
    """
    if _is_iris_focused():
        logger.info("Focus on Iris overlay — Alt+Tabbing to target window")
        pyautogui.hotkey('alt', 'tab')
        time.sleep(0.5)
        return True
    return False


def focus_browser_window(title_hint: str = "") -> bool:
    """
    Bring the browser window (Edge, Chrome, Firefox) to the foreground.
    If title_hint is provided, prefer a window whose title contains it.
    """
    try:
        import pygetwindow as gw
        # Prioritized search order
        search_terms = []
        if title_hint:
            search_terms.append(title_hint)
        search_terms += ["WhatsApp", "Edge", "Chrome", "Firefox", "Brave", "Opera"]

        for term in search_terms:
            wins = gw.getWindowsWithTitle(term)
            if wins:
                win = wins[0]
                if win.isMinimized:
                    win.restore()
                win.activate()
                time.sleep(0.55)
                logger.info("Focused window: '%s'", win.title)
                return True
    except Exception as e:
        logger.warning("pygetwindow activation failed: %s — falling back to Alt+Tab", e)

    # Fallback: Alt+Tab
    pyautogui.hotkey('alt', 'tab')
    time.sleep(0.55)
    return True


# ──────────────────────────────────────────────────────────────
# WHATSAPP WEB MESSAGING
# ──────────────────────────────────────────────────────────────

def send_whatsapp_message(contact: str, message: str, lang: str = "en") -> bool:
    """
    Full automation flow for sending a WhatsApp Web message:
      1. Focus the browser (with WhatsApp Web open)
      2. Click on the search bar
      3. Search for the contact
      4. Select the first matching chat
      5. Type the message
      6. Press Enter to send
    """
    contact = contact.strip()
    message = message.strip()
    if not contact or not message:
        speak("I need both a contact name and a message to send." if lang != "hi"
              else "मुझे संपर्क और संदेश दोनों चाहिए।", lang=lang)
        return False

    notify(f"Sending '{message}' to {contact} on WhatsApp...")
    speak(f"Sending message to {contact}" if lang != "hi"
          else f"{contact} को मेसेज भेज रहा हूँ", lang=lang)

    try:
        import pyperclip

        # ── Step 1: Focus browser with WhatsApp ──
        focus_browser_window("WhatsApp")
        time.sleep(0.5)

        # ── Step 2: Press Escape to close any open panels/search ──
        pyautogui.press('escape')
        time.sleep(0.3)

        # ── Step 3: Click on WhatsApp search bar ──
        # Try OCR-based click first for accuracy
        search_clicked = False
        try:
            from . import screen_actions
            search_clicked = screen_actions.click_element(
                "Search or start a new chat", nth=1, lang=lang
            )
        except Exception:
            pass

        if not search_clicked:
            # Fallback: use WhatsApp Web keyboard shortcut
            # Ctrl+/ is the WhatsApp Web shortcut for search on some versions
            # Or just click the search input area directly
            try:
                from . import screen_actions
                search_clicked = screen_actions.click_element("Search", nth=1, lang=lang)
            except Exception:
                pass

        if not search_clicked:
            # Last resort: use keyboard navigation
            # Tab to search bar — but this is fragile; try clicking at top area
            logger.warning("OCR search bar click failed, using Ctrl+Alt+/ fallback")
            pyautogui.press('escape')
            time.sleep(0.2)
            # WhatsApp Web focuses the search when you start typing after Escape
            # Actually, we need to click the search — use a reasonable screen position
            # The search bar is typically at y~107 in the left panel
            pyautogui.click(240, 107)

        time.sleep(0.5)

        # ── Step 4: Clear any previous search and type contact name ──
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        pyperclip.copy(contact)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(2.0)  # Wait for search results to populate

        # ── Step 5: Select the first search result ──
        pyautogui.press('down')
        time.sleep(0.3)
        pyautogui.press('enter')
        time.sleep(1.5)  # Wait for chat to load and message input to focus

        # ── Step 6: Type the message ──
        # After opening a chat, the message input box is auto-focused in WhatsApp Web
        pyperclip.copy(message)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.3)

        # ── Step 7: Send the message ──
        pyautogui.press('enter')

        speak(f"Message sent to {contact}" if lang != "hi"
              else f"{contact} को मेसेज भेज दिया", lang=lang)
        notify(f"✅ Sent to {contact}: '{message}'")
        return True

    except Exception as e:
        logger.error("WhatsApp send failed: %s", e, exc_info=True)
        notify(f"Failed to send message: {e}", success=False)
        speak("Sorry, I couldn't send the message." if lang != "hi"
              else "माफ़ करें, मेसेज नहीं भेज पाया।", lang=lang)
        return False
