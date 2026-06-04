"""Tests for ``download_tracks_in_passes`` — the two-pass track download used by
``dl.result()`` when ``--skip-subtitle-errors`` is set.

The behaviour under test is the cancel-event interaction: a failed track sets the
process-global ``DOWNLOAD_CANCELLED`` event, which makes other in-flight tracks
early-return without raising. Running the fatal video/audio tracks to completion
*before* the skippable subtitles removes that race, so a subtitle failure can no
longer truncate the video/audio that still gets muxed.
"""

from __future__ import annotations

import pytest

from unshackle.commands.dl import download_tracks_in_passes
from unshackle.core.constants import DOWNLOAD_CANCELLED
from unshackle.core.tracks import Audio, Subtitle, Video


def make_video(track_id: str = "v") -> Video:
    return Video(
        id_=track_id,
        url=f"https://example.test/{track_id}.m3u8",
        language="en",
        codec=Video.Codec.AVC,
        range_=Video.Range.SDR,
        width=1920,
        height=1080,
        bitrate=5_000_000,
    )


def make_audio(track_id: str = "a") -> Audio:
    return Audio(
        id_=track_id,
        url=f"https://example.test/{track_id}.m3u8",
        language="en",
        codec=Audio.Codec.AAC,
        bitrate=128_000,
    )


def make_subtitle(track_id: str, language: str) -> Subtitle:
    return Subtitle(
        id_=track_id,
        url=f"https://example.test/{track_id}.vtt",
        language=language,
        codec=Subtitle.Codec.WebVTT,
    )


class Harness:
    """Mimics how ``dl.result`` drives the helper, with a controllable downloader.

    ``run_one`` mirrors ``Track.download``: it early-returns (without recording a
    completion) when the cancel event is already set, and a track flagged to fail
    sets the event and raises — exactly what the real cancel sites do.
    """

    def __init__(self, fail_ids: set[str]):
        self.fail_ids = fail_ids
        self.completed: list[str] = []
        self.early_returned: list[str] = []
        self.skipped: list[Subtitle] = []

    def run_one(self, track, _index):
        if DOWNLOAD_CANCELLED.is_set():
            self.early_returned.append(track.id)
            return
        if track.id in self.fail_ids:
            DOWNLOAD_CANCELLED.set()
            raise RuntimeError(f"{track.id} failed")
        self.completed.append(track.id)

    def on_subtitle_skipped(self, track):
        self.skipped.append(track)


@pytest.fixture(autouse=True)
def _clear_event():
    DOWNLOAD_CANCELLED.clear()
    yield
    DOWNLOAD_CANCELLED.clear()


def test_failed_subtitle_does_not_truncate_video_or_audio():
    """A subtitle that fails *and sets the cancel event* must not stop the video/audio."""
    video, audio = make_video(), make_audio()
    sub = make_subtitle("s-he", "he")
    h = Harness(fail_ids={"s-he"})

    download_tracks_in_passes(
        [video, audio, sub], 4, h.run_one,
        skip_subtitle_errors=True, on_subtitle_skipped=h.on_subtitle_skipped,
    )

    assert set(h.completed) == {"v", "a"}  # both fatal tracks fully downloaded
    assert h.early_returned == []  # nothing early-returned because of the subtitle
    assert h.skipped == [sub]  # the subtitle was recorded as skipped


def test_good_subtitle_kept_bad_subtitle_skipped():
    video = make_video()
    good, bad = make_subtitle("s-en", "en"), make_subtitle("s-fr", "fr")
    h = Harness(fail_ids={"s-fr"})

    download_tracks_in_passes(
        [video, good, bad], 4, h.run_one,
        skip_subtitle_errors=True, on_subtitle_skipped=h.on_subtitle_skipped,
    )

    assert "s-en" in h.completed  # the available subtitle still downloaded
    assert h.skipped == [bad]  # only the failing one was skipped


def test_subtitle_failure_stays_fatal_without_flag():
    """Default behaviour (flag off) is unchanged: a subtitle failure aborts the title."""
    video = make_video()
    sub = make_subtitle("s-he", "he")
    h = Harness(fail_ids={"s-he"})

    with pytest.raises(RuntimeError):
        download_tracks_in_passes(
            [video, sub], 4, h.run_one,
            skip_subtitle_errors=False, on_subtitle_skipped=h.on_subtitle_skipped,
        )


def test_cancel_event_is_reset_between_titles():
    """A cancel left set by a previous title must not skip this title's tracks."""
    DOWNLOAD_CANCELLED.set()
    video, audio = make_video(), make_audio()
    h = Harness(fail_ids=set())

    download_tracks_in_passes(
        [video, audio], 4, h.run_one,
        skip_subtitle_errors=True, on_subtitle_skipped=h.on_subtitle_skipped,
    )

    assert set(h.completed) == {"v", "a"}
    assert h.early_returned == []
