import os

from actions.security.sanitizer import sanitize_app_target, sanitize_url
from actions.tools.registry import (
    TOOL_REGISTRY,
    TOOL_SAFETY,
    build_tool_contracts,
    execute_tool,
    openai_tool_schemas,
)


def test_schemas_come_from_same_registry_builder():
    built = build_tool_contracts()
    assert built.keys() == TOOL_REGISTRY.keys()
    names = {item["function"]["name"] for item in openai_tool_schemas()}
    assert names == set(TOOL_REGISTRY)


def test_safety_table_covers_every_tool():
    assert set(TOOL_SAFETY) == set(TOOL_REGISTRY)
    assert TOOL_SAFETY["fs_create_file"] == "SENSITIVE"
    assert TOOL_SAFETY["browser_fill_field"] == "SENSITIVE"
    assert TOOL_SAFETY["browser_submit"] == "SENSITIVE"
    assert TOOL_SAFETY["send_message"] == "SENSITIVE"
    assert TOOL_SAFETY["fs_list_directory"] == "SAFE"


def test_direct_malicious_args_rejected_at_tool():
    trav = execute_tool("fs_create_file", {"filename": "../etc/passwd", "location": "desktop"}, skip_confirm=True)
    assert trav["ok"] is False
    assert "traversal" in trav["error"].lower()

    listed = execute_tool("fs_list_directory", {"location": "..\\windows"})
    assert listed["ok"] is False

    file_url = execute_tool("browser_navigate", {"url": "file:///C:/Windows/System32"})
    assert file_url["ok"] is False
    ok, _, reason = sanitize_url("file:///C:/Windows/System32")
    assert ok is False
    assert "file" in reason.lower() or "scheme" in reason.lower() or "Forbidden" in reason

    app = execute_tool("app_launch", {"app_name": "cmd.exe"})
    assert app["ok"] is False
    allowed, _, app_reason = sanitize_app_target("cmd.exe")
    assert allowed is False


def test_fs_list_uses_scandir_only():
    import inspect
    from actions.context_provider import fs_list_directory
    src = inspect.getsource(fs_list_directory)
    assert "os.scandir" in src
    banned = ("subprocess", "os.system", "os.popen", " os.listdir")
    for token in banned:
        assert token not in src.replace("os.scandir", "")
