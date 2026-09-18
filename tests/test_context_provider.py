from pathlib import Path

from actions.context_provider import fs_list_directory, gather_context


def test_fs_list_real_folder():
    result = fs_list_directory("desktop")
    assert result["ok"] is True
    assert result["path"]
    assert isinstance(result["entries"], list)
    print("LIVE_FOLDER_SNAPSHOT", result)


def test_missing_folder_spoken_fallback(monkeypatch):
    spoken = []
    monkeypatch.setattr(
        "actions.context_provider.safe_directories",
        lambda: {"desktop": [Path("C:/iris_missing_folder_does_not_exist")]},
    )
    monkeypatch.setattr("actions.context_provider.speak", lambda msg, lang="en": spoken.append(msg))
    snap = gather_context(folder="desktop", include_folder=True, speak_errors=True, utterance="list files")
    assert snap["folder"]["ok"] is False
    assert spoken
    assert "could not" in spoken[0].lower() or "exist" in snap["folder"]["error"].lower()


def test_knowledge_query_does_not_dump_desktop_shortcuts():
    snap = gather_context(utterance="what is two plus two", speak_errors=False)
    assert snap["folder"].get("entries") == []
    assert "task manager" in snap["allowed_apps"]


def test_no_browser_does_not_raise(monkeypatch):
    spoken = []
    monkeypatch.setattr("actions.context_provider.speak", lambda msg, lang="en": spoken.append(msg))

    def boom():
        raise RuntimeError("no browser")

    monkeypatch.setattr("actions.browser_runtime.snapshot_elements", boom)
    snap = gather_context(include_browser=True, speak_errors=True)
    assert snap["browser"]["ok"] is False
