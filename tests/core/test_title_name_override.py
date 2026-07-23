"""Pins the --title-name override: when a caller supplies an explicit display name (e.g. the bot,
from a search result the user picked), it must win over the service's fetched/fallback name for the
output filename. Guards the STING-style case where the service can't resolve the name by id and would
otherwise fall back to a generic name that then TMDB-mismatches to the wrong title."""

from __future__ import annotations

import pytest

from unshackle.commands.dl import apply_title_name_override
from unshackle.core.titles import Movie, Movies, Series
from unshackle.core.titles.episode import Episode

pytestmark = pytest.mark.unit


class _Svc:  # a service is only used as a type marker on titles
    pass


def test_override_single_movie():
    m = Movie(id_="id0001", service=_Svc, name="STING", year=2025)
    apply_title_name_override(m, "Tom and Jerry: Forbidden Compass")
    assert m.name == "Tom and Jerry: Forbidden Compass"


def test_override_movies_collection():
    ms = Movies([Movie(id_="id0aaa", service=_Svc, name="STING"), Movie(id_="id0bbb", service=_Svc, name="STING")])
    apply_title_name_override(ms, "Tom and Jerry: Forbidden Compass")
    assert [m.name for m in ms] == ["Tom and Jerry: Forbidden Compass"] * 2


def test_override_series_sets_show_title_not_episode_name():
    ep = Episode(id_="id0001", service=_Svc, title="STING", season=1, number=2, name="Eruption")
    apply_title_name_override(Series([ep]), "Pompeii: Out of Time")
    assert ep.title == "Pompeii: Out of Time"  # show title overridden
    assert ep.name == "Eruption"               # per-episode name left intact


def test_override_single_episode():
    ep = Episode(id_="id0001", service=_Svc, title="STING", season=1, number=1)
    apply_title_name_override(ep, "Pompeii: Out of Time")
    assert ep.title == "Pompeii: Out of Time"


def test_empty_name_is_a_noop():
    m = Movie(id_="id0001", service=_Svc, name="Original", year=2025)
    apply_title_name_override(m, "")
    assert m.name == "Original"
