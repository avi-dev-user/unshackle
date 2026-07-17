"""Guards the metadata-provider robustness contract.

Enrichment is best-effort: a provider whose host is unreachable (DNS failure, refused
connection) must fail fast and let the caller skip it, never stall the download behind
urllib3 retry backoff. It also pins provider priority so a keyless provider that happens
to be dead (api.imdbapi.dev) cannot gate the happy path ahead of the keyed ones.
"""

from __future__ import annotations

import pytest
import requests

from unshackle.core.providers import ALL_PROVIDERS
from unshackle.core.providers.imdbapi import IMDBApiProvider

pytestmark = pytest.mark.unit


def test_session_does_not_retry_connection_errors():
    """Connect/read failures get zero retries so a dead host fails immediately."""
    retry = IMDBApiProvider().session.get_adapter("https://x").max_retries
    assert retry.connect == 0
    assert retry.read == 0
    assert retry.status == 2  # genuine transient server responses (429/5xx) still retry


def test_priority_puts_keyless_fallback_last():
    """TMDB (keyed, reliable) leads; IMDBApi (keyless, currently dead host) is last."""
    order = [cls.NAME for cls in ALL_PROVIDERS]
    assert order[0] == "tmdb"
    assert order[-1] == "imdbapi"


def test_search_swallows_request_exceptions(monkeypatch):
    """Any transport error is caught and downgraded to None, never propagated."""
    provider = IMDBApiProvider()

    def boom(*_a, **_k):
        raise requests.ConnectionError("dns down")

    monkeypatch.setattr(provider.session, "get", boom)
    assert provider.search("Anything", 2020, "movie") is None
