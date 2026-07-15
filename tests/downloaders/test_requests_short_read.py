"""Regression tests for the segmented-download completeness guard in the requests
downloader. A short read on an HLS segment (200 OK, full Content-Length, but the body
ends early) used to be silently accepted for segmented downloads, which truncated the
muxed video. It must now be treated as a failure and, once retries are exhausted, raise
so the batch aborts instead of delivering a partial file."""
import importlib

import pytest

# The package re-exports a `requests` function, shadowing the submodule of the same name on
# attribute access - import the module object explicitly so we can patch RETRY_WAIT on it.
dl = importlib.import_module("unshackle.core.downloaders.requests")


class _Stream:
    """Minimal stand-in for a streaming HTTP response taking the iter_content path
    (neither a requests.Session nor an RnetSession, so download() uses iter_content)."""

    def __init__(self, body: bytes, content_length: int):
        self.status_code = 200
        self._body = body
        self.headers = {"Content-Length": str(content_length)}

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield self._body  # fewer bytes than Content-Length == a short read

    def close(self):
        pass


class _Session:
    def __init__(self, body: bytes, content_length: int):
        self._body = body
        self._content_length = content_length

    def get(self, url, stream=True, **kwargs):
        return _Stream(self._body, self._content_length)


def _run(save_path, segmented):
    session = _Session(body=b"x" * 10, content_length=100)  # 10 of 100 bytes
    return list(dl.download(url="https://x/seg.ts", save_path=save_path, session=session, segmented=segmented))


def test_segmented_short_read_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "RETRY_WAIT", 0)  # keep the 5 retries fast
    with pytest.raises(IOError):
        _run(tmp_path / "seg.ts", segmented=True)


def test_non_segmented_short_read_stays_lenient(tmp_path, monkeypatch):
    # A non-segmented single track keeps the old lenient return after exhausting retries,
    # so callers can still skip an optional track. It must not raise and must not report
    # the file as successfully downloaded.
    monkeypatch.setattr(dl, "RETRY_WAIT", 0)
    events = _run(tmp_path / "file.bin", segmented=False)
    assert not any("file_downloaded" in e for e in events)
