"""Tests for SubtitleCodecChoice — notably the ``original`` keep-source sentinel that
services set via the ``sub_format`` override (must not be rejected as an invalid codec)."""

from __future__ import annotations

import pytest

from unshackle.core.tracks.subtitle import Subtitle
from unshackle.core.utils.click_types import SubtitleCodecChoice

choice = SubtitleCodecChoice(Subtitle.Codec)


@pytest.mark.parametrize("value", ["original", "ORIGINAL", "Original"])
def test_original_is_kept_as_sentinel(value):
    assert choice.convert(value) == "original"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("srt", Subtitle.Codec.SubRip),
        ("ass", Subtitle.Codec.SubStationAlphav4),
        ("vtt", Subtitle.Codec.WebVTT),
        ("WVTT", Subtitle.Codec.fVTT),
    ],
)
def test_codecs_still_map(value, expected):
    assert choice.convert(value) == expected


def test_empty_is_none():
    assert choice.convert(None) is None
