"""
Iris System Actions Module - Hardware Control & System Diagnostics
===================================================================
WHAT THIS FILE DOES (Simple English):
  This module connects Iris to your computer's physical hardware. It lets you ask
  questions about your laptop's health ("how much RAM is occupied?", "what is the battery percentage?",
  "what is the time?"), adjust master audio volume (turn up, turn down, mute), take screenshots,
  and open trusted desktop applications (Notepad, Calculator, File Explorer) safely.

GREAT TECH & PACKAGES USED IN THIS FILE:
  - psutil (Python System and Process Utilities):
      * What it does: Cross-platform hardware diagnostics library.
      * Why we use it: Fetches instant, accurate RAM usage (`psutil.virtual_memory()`), CPU load
        (`psutil.cpu_percent()`), and battery percentage (`psutil.sensors_battery()`) in real-time.
  - pyautogui:
      * What it does: Hardware multimedia key injection (`volumeup`, `volumedown`, `volumemute`, `playpause`).
      * Why we use it: Changes physical volume levels without needing complex audio driver APIs.
  - os.startfile:
      * What it does: Secure Windows native application launcher.
      * Why we use it: Completely avoids dangerous `subprocess.Popen(..., shell=True)`, preventing command injection.
"""

import os
import platform
import subprocess
import time
from datetime import datetime
from .feedback import speak, notify

try:
    import pyautogui
    pyautogui.FAILSAFE = True
except Exception:
    pyautogui = None


def _press_key(name: str) -> bool:
    if pyautogui is None:
        return False
    try:
        pyautogui.press(name)
        return True
    except Exception:
        return False

def volume_up(steps: int = 3, lang: str = 'en') -> bool:
    """
    Increases system master volume.
    """
    notify(f"Increasing volume by {steps} steps")
    for _ in range(steps):
        if not _press_key('volumeup'):
            speak("Volume control is not available on this device.", lang=lang)
            return False
        time.sleep(0.05)
    return True

def volume_down(steps: int = 3, lang: str = 'en') -> bool:
    """
    Decreases system master volume.
    """
    notify(f"Decreasing volume by {steps} steps")
    for _ in range(steps):
        if not _press_key('volumedown'):
            speak("Volume control is not available on this device.", lang=lang)
            return False
        time.sleep(0.05)
    return True

def toggle_mute(lang: str = 'en') -> bool:
    """
    Toggles mute on the system master volume.
    """
    notify("Toggling audio mute")
    if not _press_key('volumemute'):
        speak("Mute is not available on this device.", lang=lang)
        return False
    return True

def play_pause_media(lang: str = 'en') -> bool:
    """
    Toggles play/pause for active media players.
    """
    notify("Toggling media playback")
    return _press_key('playpause')

def get_default_screenshots_dir() -> str:
    """
    Returns the user's native Windows Pictures/Screenshots directory.
    Falls back to User's Pictures directory, avoiding project directory clutter.
    """
    pictures_dir = os.path.join(os.path.expanduser("~"), "Pictures")
    screenshots_dir = os.path.join(pictures_dir, "Screenshots")
    if os.path.exists(pictures_dir):
        return screenshots_dir
    return os.path.expanduser("~")

def take_screenshot(save_dir: str = None, lang: str = 'en') -> str:
    """
    Captures the desktop screen and saves it as a PNG image in the user's Pictures/Screenshots folder.
    """
    target_dir = save_dir or get_default_screenshots_dir()
    os.makedirs(target_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = os.path.join(target_dir, f"screenshot_{timestamp}.png")

    notify(f"Capturing screen to {filename}")
    speak("स्क्रीनशॉट ले लिया गया है" if lang == 'hi' else "Taking screenshot", lang=lang)
    if pyautogui is None:
        speak("Screenshots are not available on this device.", lang=lang)
        return ""
    try:
        screenshot = pyautogui.screenshot()
        screenshot.save(filename)
        return filename
    except Exception:
        speak("I could not take a screenshot.", lang=lang)
        return ""

def open_app(app_name: str, lang: str = 'en') -> bool:
    """
    Launches an approved desktop application safely by name without a shell.
    """
    from .security.sanitizer import sanitize_app_target
    ok, target, reason = sanitize_app_target(app_name)
    if not ok:
        notify(f"Security Alert: {reason}", success=False)
        speak("यह एप्लिकेशन चलाने की अनुमति नहीं है।" if lang == 'hi' else "That application is not authorized for launch.", lang=lang)
        return False

    if platform.system() != "Windows":
        speak("Opening apps this way is only supported on Windows.", lang=lang)
        return False

    clean_name = app_name.lower().strip()
    notify(f"Launching application: {clean_name}")
    speak(f"{clean_name} खोल रहा हूँ" if lang == 'hi' else f"Opening {clean_name}", lang=lang)

    try:
        if hasattr(os, "startfile"):
            os.startfile(target)
            return True
        subprocess.Popen([target], shell=False)
        return True
    except Exception as e:
        notify(f"Failed to launch '{clean_name}': {e}", success=False)
        speak(f"{clean_name} नहीं खुल पाया" if lang == 'hi' else f"Could not open {clean_name}", lang=lang)
        return False

def lock_workstation(lang: str = 'en') -> bool:
    """
    Locks the Windows workstation for security.
    """
    notify("Locking workstation")
    speak("कंप्यूटर लॉक कर दिया गया है" if lang == 'hi' else "Locking computer", lang=lang)
    try:
        if platform.system() != "Windows":
            speak("Lock screen is only supported on Windows.", lang=lang)
            return False
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return True
    except Exception:
        speak("I could not lock the computer.", lang=lang)
        return False

def get_ram_usage(lang: str = 'en') -> str:
    """
    Reports current RAM usage and occupied percentage.
    """
    try:
        import psutil
        ram = psutil.virtual_memory()
        total_gb = ram.total / (1024 ** 3)
        used_gb = ram.used / (1024 ** 3)
        percent = ram.percent
        if lang == 'hi':
            msg = f"आपके लैपटॉप में {used_gb:.1f} GB रैम इस्तेमाल हो रही है, जो कुल {total_gb:.1f} GB का {percent}% है।"
        else:
            msg = f"Your laptop is currently using {used_gb:.1f} gigabytes of RAM, which is {percent}% of your {total_gb:.1f} gigabytes total memory."
    except Exception as e:
        msg = "रैम की जानकारी अभी उपलब्ध नहीं है।" if lang == 'hi' else "Unable to read RAM status at this moment."
    notify(msg)
    speak(msg, lang=lang)
    return msg

def get_battery_status(lang: str = 'en') -> str:
    """
    Reports laptop battery charge percentage and power state.
    """
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery:
            if lang == 'hi':
                status = "चार्ज हो रही है" if battery.power_plugged else "बैटरी पर चल रहा है"
                msg = f"लैपटॉप की बैटरी {battery.percent}% है और {status}।"
            else:
                status = "plugged in and charging" if battery.power_plugged else "running on battery power"
                msg = f"Your laptop battery is at {battery.percent}% and {status}."
        else:
            msg = "इस मशीन में बैटरी सेंसर नहीं मिला।" if lang == 'hi' else "No battery sensor detected on this machine."
    except Exception:
        msg = "बैटरी की जानकारी उपलब्ध नहीं है।" if lang == 'hi' else "Unable to read battery status at this moment."
    notify(msg)
    speak(msg, lang=lang)
    return msg

def get_cpu_usage(lang: str = 'en') -> str:
    """
    Reports current CPU utilization percentage.
    """
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.2)
        if lang == 'hi':
            msg = f"वर्तमान सीपीयू उपयोग {cpu}% है।"
        else:
            msg = f"Current CPU utilization is {cpu}%."
    except Exception:
        msg = "सीपीयू उपयोग की जानकारी उपलब्ध नहीं है।" if lang == 'hi' else "Unable to read CPU usage at this moment."
    notify(msg)
    speak(msg, lang=lang)
    return msg

def get_current_time(lang: str = 'en') -> str:
    """
    Reports the current clock time.
    """
    now = datetime.now()
    time_str = now.strftime("%I:%M %p")
    if lang == 'hi':
        msg = f"अभी समय {time_str} हुआ है।"
    else:
        msg = f"The current time is {time_str}."
    notify(msg)
    speak(msg, lang=lang)
    return msg

def get_current_date(lang: str = 'en') -> str:
    """
    Reports today's calendar date.
    """
    now = datetime.now()
    date_str = now.strftime("%A, %B %d, %Y")
    if lang == 'hi':
        msg = f"आज की तारीख {date_str} है।"
    else:
        msg = f"Today is {date_str}."
    notify(msg)
    speak(msg, lang=lang)
    return msg

def type_text(text_to_type: str, press_enter: bool = False, lang: str = 'en') -> bool:
    """
    Types text into the currently focused window or application field.
    """
    clean_text = text_to_type.strip()
    if not clean_text:
        return False

    notify(f"Typing: '{clean_text}'")
    speak("Typing text")
    if pyautogui is None:
        speak("Typing is not available on this device.", lang=lang)
        return False
    try:
        import pyperclip
        pyperclip.copy(clean_text)
        time.sleep(0.3)
        pyautogui.hotkey('ctrl', 'v')
        if press_enter:
            time.sleep(0.1)
            pyautogui.press('enter')
        return True
    except Exception:
        try:
            pyautogui.write(clean_text, interval=0.02)
            if press_enter:
                pyautogui.press('enter')
            return True
        except Exception:
            speak("I could not type that text.", lang=lang)
            return False
