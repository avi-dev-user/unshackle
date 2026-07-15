"""Resolve a Hebrew-scripted title to its English display title via TMDB.

Local/foreign-language services name titles in their own script (e.g. STING/MAKO in
Hebrew). For a scene-style English filename we look the title up on TMDB and use its
English `name`/`title`, matched against the Hebrew `original_name`/`original_title` so an
ambiguous query resolves to the right entry (e.g. "הבוגדים" -> "The Traitors Israel", not
the unrelated US "The Traitors"). No-ops without a TMDB key or for a non-Hebrew title, and
returns None whenever it can't confidently resolve - callers then keep the original title.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

import requests

from unshackle.core.config import config

_HEBREW_RE = re.compile(r"[֐-׿]")


def _has_hebrew(text: str) -> bool:
    return bool(_HEBREW_RE.search(text or ""))


@lru_cache(maxsize=1024)
def resolve_english_title(title: str, year: Optional[int], kind: str) -> Optional[str]:
    """TMDB English title for a Hebrew title, or None to keep the original.

    kind is unshackle's title kind ("movie" for films, anything else -> TV). Cached per
    (title, year, kind) so a whole series is only looked up once.
    """
    title = (title or "").strip()
    if not config.tmdb_api_key or not _has_hebrew(title):
        return None

    media = "movie" if kind == "movie" else "tv"
    name_key, orig_key = ("title", "original_title") if media == "movie" else ("name", "original_name")

    params: dict[str, str | int] = {"api_key": config.tmdb_api_key, "query": title}
    if year and media == "movie":
        params["year"] = year  # reliable for films; a TV show's episodes span years, so skip it there

    try:
        r = requests.get(f"https://api.themoviedb.org/3/search/{media}", params=params, timeout=15)
        r.raise_for_status()
        results = r.json().get("results") or []
    except (requests.RequestException, ValueError):
        return None
    if not results:
        return None

    # Prefer an exact Hebrew original-title match - disambiguates same-named entries.
    exact = [item for item in results if (item.get(orig_key) or "").strip() == title]
    pick = (exact or results)[0]

    english = (pick.get(name_key) or "").strip()
    # Only use a genuinely English result; if TMDB's display name is itself Hebrew there's
    # nothing gained, so keep the original.
    if english and not _has_hebrew(english):
        return english
    return None
