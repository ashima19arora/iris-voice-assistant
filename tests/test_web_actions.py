from actions.security.sanitizer import sanitize_url


def test_gov_in_maps_to_https():
    ok, url, _ = sanitize_url("gov.in")
    assert ok
    assert url.startswith("https://")
    assert "india.gov.in" in url


def test_https_youtube_allowed():
    ok, url, _ = sanitize_url("youtube")
    assert ok
    assert url == "https://www.youtube.com"


def test_file_scheme_blocked():
    ok, url, reason = sanitize_url("file:///C:/Windows/System32")
    assert not ok
    assert url == ""
    assert "scheme" in reason.lower() or "protocol" in reason.lower() or "forbidden" in reason.lower()


def test_javascript_scheme_blocked():
    ok, _, _ = sanitize_url("javascript:alert(1)")
    assert not ok


def test_localhost_blocked():
    ok, _, _ = sanitize_url("http://127.0.0.1/admin")
    assert not ok
