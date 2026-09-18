from pathlib import Path

import pytest

from actions.confirmation import parse_confirmation, request_confirmation
from actions.file_actions import (
    UnsafeFileName,
    create_file,
    get_target_directory,
    sanitize_file_name,
    validate_file_name,
    _is_inside_whitelist,
)


def test_validate_rejects_path_traversal_without_renaming():
    ok, name, reason = validate_file_name("../etc/passwd")
    assert ok is False
    assert name == ""
    assert "traversal" in reason.lower()
    with pytest.raises(UnsafeFileName):
        sanitize_file_name("..\\windows\\system32\\hack.txt")
    with pytest.raises(UnsafeFileName):
        sanitize_file_name("/etc/passwd")


def test_validate_rejects_forbidden_extension_without_renaming():
    ok, name, reason = validate_file_name("virus.exe")
    assert ok is False
    assert name == ""
    assert "not allowed" in reason.lower()


def test_validate_defaults_txt_for_bare_name():
    ok, name, reason = validate_file_name("notes")
    assert ok is True
    assert name == "notes.txt"


def test_desktop_path_is_whitelisted():
    desktop = Path(get_target_directory("desktop"))
    sample = desktop / "note.txt"
    assert _is_inside_whitelist(sample)


def test_create_file_cannot_write_until_confirm_true(tmp_path, monkeypatch):
    from actions import file_actions as fa

    monkeypatch.setattr(fa, "get_target_directory", lambda loc="desktop": str(tmp_path))
    monkeypatch.setattr(fa, "_is_inside_whitelist", lambda p: True)
    written = {"yes": False}

    def deny(prompt, **kwargs):
        assert not (tmp_path / "tasks.txt").exists()
        return False

    assert create_file("tasks.txt", location="desktop", confirm_fn=deny, open_after=False) is False
    assert not (tmp_path / "tasks.txt").exists()

    def allow(prompt, **kwargs):
        written["yes"] = True
        return True

    assert create_file("tasks.txt", location="desktop", confirm_fn=allow, open_after=False) is True
    assert written["yes"] is True
    assert (tmp_path / "tasks.txt").exists()


def test_confirmation_yes_phrases_and_timeout_is_no():
    assert parse_confirmation("yes")
    assert parse_confirmation("yeah")
    assert parse_confirmation("sure")
    assert parse_confirmation("go ahead")
    assert parse_confirmation("do it")
    assert not parse_confirmation("no")
    assert not parse_confirmation("maybe")
    assert not parse_confirmation("")
    assert request_confirmation("ok?", listen_fn=lambda timeout=8: None) is False
    assert request_confirmation("ok?", listen_fn=lambda timeout=8: "nope") is False
    assert request_confirmation("ok?", listen_fn=lambda timeout=8: "yes") is True
    from actions.config import CONFIRMATION_TIMEOUT_SEC
    assert CONFIRMATION_TIMEOUT_SEC == 8.0
