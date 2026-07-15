"""Tests for the Hebrew -> English title resolver (TMDB-backed, used for scene-style
filenames). Network is mocked; the point is the guards and the disambiguation, not TMDB."""
import pytest

import unshackle.core.utils.english_title as et


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _clear_cache():
    et.resolve_english_title.cache_clear()
    yield
    et.resolve_english_title.cache_clear()


def _set_key(monkeypatch, key):
    monkeypatch.setattr(et.config, "tmdb_api_key", key, raising=False)


def test_no_key_keeps_original(monkeypatch):
    _set_key(monkeypatch, "")
    assert et.resolve_english_title("הבוגדים", None, "tv") is None


def test_non_hebrew_is_untouched(monkeypatch):
    # A non-Hebrew title must never trigger a lookup at all (zero blast radius).
    _set_key(monkeypatch, "k")
    called = False

    def _boom(*a, **k):
        nonlocal called
        called = True
        raise AssertionError("should not hit the network for a non-Hebrew title")

    monkeypatch.setattr(et.requests, "get", _boom)
    assert et.resolve_english_title("The Office", None, "tv") is None
    assert called is False


def test_disambiguates_on_hebrew_original_name(monkeypatch):
    _set_key(monkeypatch, "k")
    payload = {"results": [
        {"name": "The Traitors", "original_name": "The Traitors"},               # US, wrong
        {"name": "The Traitors Israel", "original_name": "הבוגדים"},              # IL, right
    ]}
    monkeypatch.setattr(et.requests, "get", lambda *a, **k: _Resp(payload))
    assert et.resolve_english_title("הבוגדים", None, "tv") == "The Traitors Israel"


def test_falls_back_when_display_name_still_hebrew(monkeypatch):
    _set_key(monkeypatch, "k")
    payload = {"results": [{"name": "פאודה", "original_name": "פאודה"}]}
    monkeypatch.setattr(et.requests, "get", lambda *a, **k: _Resp(payload))
    assert et.resolve_english_title("פאודה", None, "tv") is None


def test_no_results_keeps_original(monkeypatch):
    _set_key(monkeypatch, "k")
    monkeypatch.setattr(et.requests, "get", lambda *a, **k: _Resp({"results": []}))
    assert et.resolve_english_title("סדרה שלא קיימת", None, "tv") is None
