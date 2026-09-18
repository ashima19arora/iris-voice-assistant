"""Playwright browser session used by context_provider and planner tools."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("iris")

_playwright = None
_browser = None
_page = None


def _ensure_page():
    global _playwright, _browser, _page
    if _page is not None:
        return _page
    from playwright.sync_api import sync_playwright

    _playwright = sync_playwright().start()
    _browser = _playwright.chromium.launch(headless=True)
    _page = _browser.new_page()
    return _page


def get_page():
    return _ensure_page()


def close_browser() -> None:
    global _playwright, _browser, _page
    try:
        if _browser:
            _browser.close()
    except Exception:
        pass
    try:
        if _playwright:
            _playwright.stop()
    except Exception:
        pass
    _playwright = None
    _browser = None
    _page = None


def snapshot_elements(timeout_ms: int = 2000) -> Dict[str, Any]:
    """Accessibility/DOM roles and names — not OCR."""
    try:
        page = get_page()
        page.wait_for_timeout(50)
        tree = page.evaluate(
            """() => {
                const out = [];
                const nodes = document.querySelectorAll('a, button, input, textarea, [role]');
                for (const el of nodes) {
                    if (out.length >= 40) break;
                    const role = el.getAttribute('role') || el.tagName.toLowerCase();
                    const name = (el.getAttribute('aria-label') || el.innerText || el.getAttribute('placeholder') || el.getAttribute('name') || '').trim().slice(0, 80);
                    out.push({role, name, tag: el.tagName.toLowerCase()});
                }
                return out;
            }"""
        )
        elements: List[Dict[str, str]] = []
        for i, node in enumerate(tree or []):
            elements.append({
                "tag": node.get("tag") or node.get("role") or "",
                "name": (node.get("name") or "").strip(),
                "selector": f"{node.get('tag') or 'div'} >> nth={i}",
                "role": node.get("role") or "",
            })
        return {
            "ok": True,
            "url": page.url,
            "title": page.title(),
            "accessibility_role": "document",
            "accessibility_name": page.title(),
            "elements": elements,
            "error": "",
        }
    except Exception as exc:
        logger.warning("browser snapshot unavailable: %s", exc)
        return {
            "ok": False,
            "url": "",
            "title": "",
            "accessibility_role": "",
            "accessibility_name": "",
            "elements": [],
            "error": "No active browser window.",
        }


def navigate(url: str) -> Dict[str, Any]:
    page = get_page()
    page.goto(url, wait_until="domcontentloaded", timeout=15000)
    return {"ok": True, "url": page.url, "title": page.title()}


def click(selector: str) -> Dict[str, Any]:
    page = get_page()
    page.locator(selector).first.click(timeout=5000)
    return {"ok": True, "selector": selector}


def fill(selector: str, value: str) -> Dict[str, Any]:
    page = get_page()
    page.locator(selector).first.fill(value, timeout=5000)
    return {"ok": True, "selector": selector}


def submit(selector: str = "form") -> Dict[str, Any]:
    page = get_page()
    page.locator(selector).first.evaluate("el => el.requestSubmit ? el.requestSubmit() : el.submit()")
    return {"ok": True, "selector": selector}
