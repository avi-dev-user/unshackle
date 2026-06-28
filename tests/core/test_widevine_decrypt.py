"""Decrypter-selection tests for ``Widevine.decrypt``.

These lock down the routing between the two decryption backends:

- ``config.decryption == "mp4decrypt"`` forces the Bento4 path.
- Otherwise Shaka Packager is the default.
- If Shaka fails (e.g. older builds SIGSEGV on Smooth/PIFF content), decrypt
  must fall back to mp4decrypt rather than failing the whole download.
- The fallback only applies when mp4decrypt is actually available; with no
  fallback binary the original Shaka error must propagate (no silent swallow).

The two ``_decrypt_with_*`` workers are stubbed so the tests exercise the
routing logic without invoking real binaries.
"""

from __future__ import annotations

import subprocess

import pytest
from pywidevine.pssh import PSSH

from unshackle.core import binaries
from unshackle.core.config import config
from unshackle.core.drm.widevine import Widevine

KID = "2fa4d930623a401585ab00dfca7b4b29"
KEY = "6b0cce75fa87bb9ba36308f0c4d8a861"


def make_widevine() -> Widevine:
    wv = Widevine(pssh=PSSH.new(system_id=PSSH.SystemId.Widevine, key_ids=[KID]), kid=KID)
    # decrypt() refuses to run without content keys; the value is never read by the stubs.
    wv.content_keys = {kid: KEY for kid in wv.kids}
    return wv


@pytest.fixture
def enc_file(tmp_path):
    path = tmp_path / "track.mp4"
    path.write_bytes(b"\x00encrypted\x00")
    return path


@pytest.fixture(autouse=True)
def _reset_decryption():
    """decrypt() reads the shared config singleton; keep tests isolated from each other."""
    original = getattr(config, "decryption", None)
    yield
    config.decryption = original


def _record(wv, calls, *, shaka_exc=None):
    """Stub both backends to record invocation order; optionally make Shaka raise."""

    def shaka(path):
        calls.append("shaka")
        if shaka_exc is not None:
            raise shaka_exc

    def mp4decrypt(path):
        calls.append("mp4decrypt")

    wv._decrypt_with_shaka_packager = shaka
    wv._decrypt_with_mp4decrypt = mp4decrypt


def test_explicit_mp4decrypt_skips_shaka(enc_file):
    config.decryption = "mp4decrypt"
    wv = make_widevine()
    calls = []
    _record(wv, calls)
    wv.decrypt(enc_file)
    assert calls == ["mp4decrypt"]


def test_default_uses_shaka_without_fallback(enc_file):
    config.decryption = ""
    wv = make_widevine()
    calls = []
    _record(wv, calls)  # shaka succeeds
    wv.decrypt(enc_file)
    assert calls == ["shaka"]


def test_shaka_failure_falls_back_to_mp4decrypt(enc_file, monkeypatch):
    config.decryption = ""
    monkeypatch.setattr(binaries, "Mp4decrypt", "/usr/bin/mp4decrypt")
    wv = make_widevine()
    calls = []
    _record(wv, calls, shaka_exc=subprocess.CalledProcessError(-11, ["packager"]))
    wv.decrypt(enc_file)
    assert calls == ["shaka", "mp4decrypt"]


def test_shaka_failure_clears_stale_partial_output(enc_file, monkeypatch):
    config.decryption = ""
    monkeypatch.setattr(binaries, "Mp4decrypt", "/usr/bin/mp4decrypt")
    stale = enc_file.with_stem(f"{enc_file.stem}_decrypted")
    stale.write_bytes(b"partial shaka output")
    wv = make_widevine()
    calls = []
    _record(wv, calls, shaka_exc=subprocess.CalledProcessError(-11, ["packager"]))
    wv.decrypt(enc_file)
    assert calls == ["shaka", "mp4decrypt"]
    assert not stale.exists()  # cleared so mp4decrypt starts clean


def test_shaka_failure_reraises_without_mp4decrypt(enc_file, monkeypatch):
    config.decryption = ""
    monkeypatch.setattr(binaries, "Mp4decrypt", None)
    wv = make_widevine()
    calls = []
    _record(wv, calls, shaka_exc=subprocess.CalledProcessError(-11, ["packager"]))
    with pytest.raises(subprocess.CalledProcessError):
        wv.decrypt(enc_file)
    assert calls == ["shaka"]  # no fallback attempted
