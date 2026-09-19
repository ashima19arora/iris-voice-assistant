import sys
sys.path.insert(0, ".")
import win32gui
import win32process
import psutil
from actions.screen_understanding import get_active_window_info, analyze_screen_content, describe_screen
from actions.intent_parser import parse_intent

def test_screen():
    print("--- ACTIVE WINDOW ---")
    print(get_active_window_info())

    print("\n--- VISIBLE WINDOWS ---")
    windows = []
    def cb(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            txt = win32gui.GetWindowText(hwnd).strip()
            if txt:
                windows.append(txt)
        return True
    win32gui.EnumWindows(cb, None)
    for w in windows[:10]:
        print("  -", w)

    print("\n--- SCREEN ANALYSIS ---")
    analysis = analyze_screen_content()
    print("Search Query:", analysis.get("search_query"))
    print("Search Results:", analysis.get("search_results"))
    print("Highlights:", analysis.get("highlights"))

    print("\n--- DESCRIBE SCREEN ---")
    print(describe_screen(speak_aloud=False))

if __name__ == "__main__":
    test_screen()
