"""Multi-period DASH handling: descriptive-role detection and cross-period matching.

Two fixes for multi-period manifests (e.g. short ad/bumper periods around the main
content) are locked down here:

- ``is_descriptive`` must recognise an audio-description set marked with the standard
  ``<Role value="description">``. Services do not always use the ``Accessibility``
  descriptor; without this, a description set is indistinguishable from the regular
  audio of the same language and bitrate and both hash to the same track id.
- ``_match_representation_in_period`` must find the wanted track in every content
  period. Services often reuse a different Representation id per period, so matching
  on id alone truncates the download to the track's origin period.
"""

from __future__ import annotations

from lxml import etree

from unshackle.core.manifests.dash import DASH


def _el(xml: str):
    return etree.fromstring(xml)


def _period(pid: str, *, en=(70000, 137000), end=(137000,), he=(70000, 137000)) -> etree._Element:
    """Build a Period whose Representation ids are namespaced by ``pid`` so they
    differ from those in other periods, mirroring real multi-period manifests."""
    en_reps = "".join(f'<Representation id="{pid}_en_{b}" bandwidth="{b}" codecs="mp4a.40.2"/>' for b in en)
    end_reps = "".join(f'<Representation id="{pid}_end_{b}" bandwidth="{b}" codecs="mp4a.40.2"/>' for b in end)
    he_reps = "".join(f'<Representation id="{pid}_he_{b}" bandwidth="{b}" codecs="mp4a.40.2"/>' for b in he)
    return _el(
        f'<Period id="{pid}">'
        f'<AdaptationSet contentType="audio" lang="en">{en_reps}</AdaptationSet>'
        f'<AdaptationSet contentType="audio" lang="en">'
        f'<Role schemeIdUri="urn:mpeg:dash:role:2011" value="description"/>{end_reps}</AdaptationSet>'
        f'<AdaptationSet contentType="audio" lang="he">{he_reps}</AdaptationSet>'
        f'<AdaptationSet contentType="video" lang="en">'
        f'<Representation id="{pid}_v" bandwidth="2000000" codecs="avc1.640028"/></AdaptationSet>'
        f"</Period>"
    )


def _find(period, rep_id):
    """Return (adaptation_set, representation) for a Representation id in a period."""
    for as_ in period.findall("AdaptationSet"):
        for rep in as_.findall("Representation"):
            if rep.get("id") == rep_id:
                return as_, rep
    raise AssertionError(f"{rep_id} not in period")


class TestIsDescriptive:
    def test_role_description(self):
        as_ = _el(
            '<AdaptationSet lang="en"><Role schemeIdUri="urn:mpeg:dash:role:2011" value="description"/></AdaptationSet>'
        )
        assert DASH.is_descriptive(as_) is True

    def test_role_descriptive(self):
        as_ = _el(
            '<AdaptationSet lang="en"><Role schemeIdUri="urn:mpeg:dash:role:2011" value="descriptive"/></AdaptationSet>'
        )
        assert DASH.is_descriptive(as_) is True

    def test_accessibility_still_detected(self):
        as_ = _el(
            '<AdaptationSet lang="en">'
            '<Accessibility schemeIdUri="urn:tva:metadata:cs:AudioPurposeCS:2007" value="1"/></AdaptationSet>'
        )
        assert DASH.is_descriptive(as_) is True

    def test_plain_audio_not_descriptive(self):
        as_ = _el('<AdaptationSet lang="en"><Role schemeIdUri="urn:mpeg:dash:role:2011" value="main"/></AdaptationSet>')
        assert DASH.is_descriptive(as_) is False


class TestMatchRepresentationInPeriod:
    def test_exact_id_wins(self):
        src = _period("p1")
        as_, rep = _find(src, "p1_he_137000")
        m_as, m_rep = DASH._match_representation_in_period(
            src, rep_id="p1_he_137000", adaptation_set=as_, representation=rep
        )
        assert m_rep.get("id") == "p1_he_137000"

    def test_cross_period_matches_language_and_closest_bitrate(self):
        # Track originates in p1; the same logical track has different ids and
        # slightly different bandwidths in p2.
        src = _period("p1", he=(70000, 137000))
        tgt = _period("p2", he=(57000, 136500))
        as_, rep = _find(src, "p1_he_137000")
        m_as, m_rep = DASH._match_representation_in_period(
            tgt, rep_id="p1_he_137000", adaptation_set=as_, representation=rep
        )
        assert m_as.get("lang") == "he"
        assert m_rep.get("id") == "p2_he_136500"  # closest rung, not the 57000 one

    def test_descriptive_does_not_match_regular_audio(self):
        # Origin is the English audio-description set; it must match only the
        # description set in the target period, never the regular English audio.
        src = _period("p1")
        tgt = _period("p2")
        as_, rep = _find(src, "p1_end_137000")
        assert DASH.is_descriptive(as_) is True
        m_as, m_rep = DASH._match_representation_in_period(
            tgt, rep_id="p1_end_137000", adaptation_set=as_, representation=rep
        )
        assert DASH.is_descriptive(m_as) is True
        assert m_rep.get("id") == "p2_end_137000"

    def test_regular_audio_does_not_match_descriptive(self):
        # Mirror: a regular English track must not be served the description set.
        src = _period("p1")
        tgt = _period("p2")
        as_, rep = _find(src, "p1_en_137000")
        assert DASH.is_descriptive(as_) is False
        m_as, m_rep = DASH._match_representation_in_period(
            tgt, rep_id="p1_en_137000", adaptation_set=as_, representation=rep
        )
        assert DASH.is_descriptive(m_as) is False
        assert m_as.get("lang") == "en"
        assert m_rep.get("id") == "p2_en_137000"

    def test_no_match_returns_none(self):
        src = _period("p1")
        as_, rep = _find(src, "p1_he_137000")
        video_only = _el(
            '<Period id="p3"><AdaptationSet contentType="video" lang="en">'
            '<Representation id="p3_v" bandwidth="2000000" codecs="avc1.640028"/></AdaptationSet></Period>'
        )
        m_as, m_rep = DASH._match_representation_in_period(
            video_only, rep_id="p1_he_137000", adaptation_set=as_, representation=rep
        )
        assert (m_as, m_rep) == (None, None)

    def test_video_matches_resolution_not_just_bitrate(self):
        # Period bandwidths drift: the 1080p rung's bandwidth in p2 is *closer* to p1's 720p
        # bandwidth than to p1's 1080p bandwidth. Matching on bandwidth alone would pull 720p;
        # matching on height must keep 1080p.
        src = _el(
            '<Period id="p1"><AdaptationSet contentType="video" lang="en">'
            '<Representation id="p1_v720" width="1280" height="720" bandwidth="1500000" codecs="avc1.4d401f"/>'
            '<Representation id="p1_v1080" width="1920" height="1080" bandwidth="3900000" codecs="avc1.640028"/>'
            "</AdaptationSet></Period>"
        )
        tgt = _el(
            '<Period id="p2"><AdaptationSet contentType="video" lang="en">'
            '<Representation id="p2_v720" width="1280" height="720" bandwidth="1400000" codecs="avc1.4d401f"/>'
            '<Representation id="p2_v1080" width="1920" height="1080" bandwidth="1600000" codecs="avc1.640028"/>'
            "</AdaptationSet></Period>"
        )
        as_, rep = _find(src, "p1_v1080")
        m_as, m_rep = DASH._match_representation_in_period(
            tgt, rep_id="p1_v1080", adaptation_set=as_, representation=rep
        )
        assert m_rep.get("height") == "1080"
        assert m_rep.get("id") == "p2_v1080"


class TestPeriodDurationSeconds:
    def test_minutes_seconds(self):
        assert DASH._period_duration_seconds(_el('<Period duration="PT21M42.000S"/>')) == 21 * 60 + 42

    def test_hours_minutes_seconds(self):
        assert DASH._period_duration_seconds(_el('<Period duration="PT1H2M3S"/>')) == 3723

    def test_short_bumper(self):
        assert DASH._period_duration_seconds(_el('<Period duration="PT2.990S"/>')) == 2.99

    def test_missing_duration_is_zero(self):
        assert DASH._period_duration_seconds(_el('<Period id="x"/>')) == 0.0

    def test_longest_period_is_the_main_content(self):
        # The main content period must win over short ident/bumper periods.
        periods = [
            _el('<Period id="seq:-1_0" duration="PT2.990S"/>'),
            _el('<Period id="seq:0_0" duration="PT21M42.000S"/>'),
            _el('<Period id="seq:1_0" duration="PT10.000S"/>'),
        ]
        main = max(periods, key=DASH._period_duration_seconds)
        assert main.get("id") == "seq:0_0"
