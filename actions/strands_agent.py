"""
Iris AWS Strands Agent Module
==============================
Integrates AWS Strands Agents SDK (https://strandsagents.com, aws/strands-agents)
to provide model-driven agentic reasoning and tool invocation for Iris.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from strands import tool

logger = logging.getLogger("IrisStrandsAgent")


# ------------------------------------------------------------------------------
# 1. TOOL DEFINITIONS DECORATED WITH @tool FOR AWS STRANDS AGENTS
# ------------------------------------------------------------------------------

@tool
def check_system_memory() -> str:
    """Check current system RAM utilization on the host computer."""
    from .system_actions import get_ram_usage
    ram = get_ram_usage()
    return f"RAM usage is {ram.get('percent', 0)}% ({ram.get('used_gb', 0):.1f} GB used of {ram.get('total_gb', 0):.1f} GB)."


@tool
def open_application(app_name: str) -> str:
    """Launch an approved desktop application on Windows.
    Args:
        app_name: Name of the application (e.g. 'notepad', 'calculator', 'settings', 'task manager').
    """
    from .system_actions import launch_app
    success = launch_app(app_name)
    return f"Successfully opened {app_name}." if success else f"Failed to open {app_name}."


@tool
def search_internet(query: str) -> str:
    """Search Google or the web for a query.
    Args:
        query: What to search for.
    """
    from .browser_actions import search_web
    success = search_web(query)
    return f"Searched the web for: {query}" if success else f"Failed to search for: {query}"


@tool
def open_website(url_or_site: str) -> str:
    """Navigate to a website URL or named domain.
    Args:
        url_or_site: Target URL or site name (e.g. 'youtube.com', 'gov.in').
    """
    from .browser_actions import open_url
    target = url_or_site if url_or_site.startswith("http") else f"https://{url_or_site}"
    success = open_url(target)
    return f"Navigated to {target}." if success else f"Failed to open {target}."


@tool
def inspect_screen() -> str:
    """Read the active window and screen content aloud using Windows UI Automation and OCR."""
    from .screen_understanding import describe_screen
    description = describe_screen(speak_aloud=False)
    return f"Screen summary: {description}"


@tool
def fill_form_field(text: str) -> str:
    """Enters text into the focused form field via safe clipboard injection.
    Args:
        text: The text string to enter.
    """
    from .form_actions import fill_field
    success = fill_field(text)
    return f"Filled field with: '{text}'." if success else "Failed to enter text."


@tool
def click_screen_element(target: str) -> str:
    """Clicks an element, link, or button on the screen identified by text or label.
    Args:
        target: The text or label of the element to click.
    """
    from .screen_actions import click_element_by_text
    success = click_element_by_text(target)
    return f"Clicked on {target}." if success else f"Could not find {target} on screen."


@tool
def adjust_volume(direction: str = "up", steps: int = 3) -> str:
    """Changes speaker volume.
    Args:
        direction: 'up', 'down', or 'mute'.
        steps: Number of volume steps to adjust.
    """
    from .system_actions import set_volume
    success = set_volume(action=direction, steps=steps)
    return f"Volume adjusted: {direction}." if success else "Failed to adjust volume."


# Registered Strands Tool List
IRIS_STRANDS_TOOLS = [
    check_system_memory,
    open_application,
    search_internet,
    open_website,
    inspect_screen,
    fill_form_field,
    click_screen_element,
    adjust_volume,
]

STRANDS_SYSTEM_PROMPT = """You are Iris, a hands-free voice operating layer for Windows.
You help visually impaired and accessibility users navigate their computer.
You have access to tools for opening applications, searching the web, filling forms,
inspecting the screen, and checking system health.
Always invoke the most direct tool to accomplish the user's intent.
"""


def create_iris_strands_agent(model: Any = None):
    """
    Initializes an AWS Strands Agent instance configured with Iris accessibility tools.
    """
    try:
        from strands import Agent
        agent = Agent(
            tools=IRIS_STRANDS_TOOLS,
            system_prompt=STRANDS_SYSTEM_PROMPT,
        )
        return agent
    except Exception as exc:
        logger.warning("Could not initialize full Strands Agent: %s", exc)
        return None
