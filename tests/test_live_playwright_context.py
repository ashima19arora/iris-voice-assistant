"""Live Playwright accessibility snapshot (not OCR)."""
from actions import browser_runtime
from actions.context_provider import fs_list_directory


def test_live_playwright_accessibility_tree():
    browser_runtime.navigate("https://example.com")
    snap = browser_runtime.snapshot_elements()
    assert snap["ok"] is True
    assert "example" in (snap.get("url") or "").lower() or "example" in (snap.get("title") or "").lower()
    assert snap["elements"], snap
    print("LIVE_BROWSER_SNAPSHOT", snap)
    folder = fs_list_directory("desktop")
    print("LIVE_FOLDER_SNAPSHOT", folder)
    assert folder["ok"]
    browser_runtime.close_browser()
