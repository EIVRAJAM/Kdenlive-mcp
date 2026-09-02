from pathlib import Path
import xml.etree.ElementTree as ET

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
RECON_DIR = REPO_ROOT / "examples" / "recon"


REFERENCE_PROJECTS = [
    "manual_empty_vertical.kdenlive",
    "manual_bin_only.kdenlive",
    "manual_two_clips_timeline.kdenlive",
    "manual_trim_marker.kdenlive",
]

# Additional fixtures require manual creation in Kdenlive. The tests below skip
# until each file exists. Manual recipes are documented in
# docs/KDENLIVE_PROJECT_FORMAT.md.
ADDITIONAL_REFERENCE_PROJECTS = [
    "manual_trimmed_clip.kdenlive",
    "manual_gap_timeline.kdenlive",
    "manual_transition_dissolve.kdenlive",
    "manual_basic_effect.kdenlive",
]

DEFAULT_TRANSITION_SERVICES = {"mix", "qtblend"}
DEFAULT_FILTER_SERVICES = {"volume", "panner", "audiolevel"}


def _props(element: ET.Element) -> dict[str, str]:
    return {
        prop.attrib["name"]: prop.text or ""
        for prop in element.findall("property")
        if "name" in prop.attrib
    }


def _parse(name: str) -> ET.Element:
    return ET.parse(RECON_DIR / name).getroot()


def _time_to_frames(timecode: str, fps: float = 30.0) -> int:
    if not timecode:
        return 0
    hours, minutes, rest = timecode.split(":")
    seconds, millis = rest.split(".")
    total = int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000
    return round(total * fps)


def _has_trimmed_clip(root: ET.Element) -> bool:
    for playlist in root.findall("playlist"):
        for entry in playlist.findall("entry"):
            if entry.get("in") not in (None, "00:00:00.000"):
                return True
    return False


def _has_real_gap(root: ET.Element) -> bool:
    for playlist in root.findall("playlist"):
        for blank in playlist.findall("blank"):
            if _time_to_frames(blank.get("length", "00:00:00.000")) > 0:
                return True
    # Entry in/out attributes are SOURCE ranges, not timeline positions, so
    # "out < following in" is not a confirmed gap signal for Kdenlive 26.04.3.
    # A future fallback would need to accumulate playlist lengths and blanks;
    # it is intentionally not used yet:
    #   for current, following in zip(entries, entries[1:]):
    #       if _time_to_frames(current.get("out")) < _time_to_frames(following.get("in")):
    #           return True
    return False


def _has_dissolve_transition(root: ET.Element) -> bool:
    for transition in root.iter("transition"):
        service = _props(transition).get("mlt_service")
        if transition.get("in") is not None and transition.get("out") is not None:
            return True
        if service not in DEFAULT_TRANSITION_SERVICES:
            return True
    return False


def _has_basic_effect(root: ET.Element) -> bool:
    for filter_ in root.iter("filter"):
        props = _props(filter_)
        service = props.get("mlt_service")
        if service and service not in DEFAULT_FILTER_SERVICES:
            return True
    return False


def _skip_when_missing(names: list[str]):
    return [
        pytest.param(
            name,
            marks=pytest.mark.skipif(
                not (RECON_DIR / name).exists(),
                reason=f"{name} requires manual creation in Kdenlive; recipe in docs/KDENLIVE_PROJECT_FORMAT.md",
            ),
        )
        for name in names
    ]


def test_manual_kdenlive_reference_projects_are_well_formed() -> None:
    for name in REFERENCE_PROJECTS:
        root = _parse(name)

        assert root.tag == "mlt"
        assert root.attrib["producer"] == "main_bin"
        assert root.attrib["version"] == "7.40.0"


def test_manual_projects_use_vertical_hd_30_profile() -> None:
    for name in REFERENCE_PROJECTS:
        profile = _parse(name).find("profile")

        assert profile is not None
        assert profile.attrib["width"] == "1080"
        assert profile.attrib["height"] == "1920"
        assert profile.attrib["frame_rate_num"] == "30"
        assert profile.attrib["frame_rate_den"] == "1"
        assert profile.attrib["display_aspect_num"] == "9"
        assert profile.attrib["display_aspect_den"] == "16"


def test_main_bin_contains_document_properties_and_sequence() -> None:
    for name in REFERENCE_PROJECTS:
        main_bin = _parse(name).find("playlist[@id='main_bin']")

        assert main_bin is not None
        props = _props(main_bin)
        assert props["kdenlive:docproperties.kdenliveversion"] == "26.04.3"
        assert props["kdenlive:docproperties.profile"] == "vertical_hd_30"
        assert props["kdenlive:docproperties.version"] == "1.1"
        assert main_bin.find("entry[@producer='tractor4']") is not None


def test_imported_media_uses_chains_with_stable_kdenlive_ids() -> None:
    root = _parse("manual_bin_only.kdenlive")
    chains = {
        _props(chain).get("resource"): _props(chain).get("kdenlive:id")
        for chain in root.findall("chain")
    }

    assert chains["sample_vertical.mp4"] == "4"
    assert chains["sample1.mp4"] == "5"


def test_timeline_audio_video_entries_reference_same_kdenlive_media_ids() -> None:
    root = _parse("manual_two_clips_timeline.kdenlive")
    playlist0 = root.find("playlist[@id='playlist0']")
    playlist6 = root.find("playlist[@id='playlist6']")

    assert playlist0 is not None
    assert playlist6 is not None
    assert _props(playlist0)["kdenlive:audio_track"] == "1"

    audio_ids = [_props(entry)["kdenlive:id"] for entry in playlist0.findall("entry")]
    video_ids = [_props(entry)["kdenlive:id"] for entry in playlist6.findall("entry")]

    assert audio_ids == ["4", "5"]
    assert video_ids == ["4", "5"]


def test_manual_marker_project_contains_hook_guide_and_marker() -> None:
    root = _parse("manual_trim_marker.kdenlive")
    sequence = root.find("tractor[@id='tractor4']")

    assert sequence is not None
    props = _props(sequence)
    assert '"comment": "hook"' in props["kdenlive:sequenceproperties.guides"]
    assert '"comment": "hook"' in props["kdenlive:markers"]


def test_existing_reference_projects_have_no_trim_or_gap() -> None:
    for name in REFERENCE_PROJECTS:
        root = _parse(name)

        assert _has_trimmed_clip(root) is False
        assert _has_real_gap(root) is False


def test_existing_reference_projects_have_no_playlist_blanks() -> None:
    for name in REFERENCE_PROJECTS:
        root = _parse(name)

        for playlist in root.findall("playlist"):
            assert playlist.findall("blank") == []


def test_existing_reference_projects_have_only_default_transitions_and_filters() -> None:
    for name in REFERENCE_PROJECTS:
        root = _parse(name)

        for transition in root.iter("transition"):
            assert _props(transition).get("mlt_service") in DEFAULT_TRANSITION_SERVICES
            assert _props(transition).get("internal_added") == "237"
        for filter_ in root.iter("filter"):
            assert _props(filter_).get("mlt_service") in DEFAULT_FILTER_SERVICES
            assert _props(filter_).get("disable") == "1"
            assert _props(filter_).get("internal_added") == "237"


@pytest.mark.parametrize("name", _skip_when_missing(ADDITIONAL_REFERENCE_PROJECTS))
def test_additional_fixture_is_well_formed_with_existing_media(name: str) -> None:
    root = _parse(name)

    assert root.tag == "mlt"
    assert root.attrib["producer"] == "main_bin"
    for chain in root.findall("chain"):
        resource = _props(chain).get("resource")
        if resource and resource != "black":
            assert (RECON_DIR / resource).exists()


@pytest.mark.parametrize("name", _skip_when_missing(["manual_trimmed_clip.kdenlive"]))
def test_trimmed_clip_fixture_contains_visible_trim(name: str) -> None:
    assert _has_trimmed_clip(_parse(name))


@pytest.mark.parametrize("name", _skip_when_missing(["manual_gap_timeline.kdenlive"]))
def test_gap_timeline_fixture_contains_real_temporal_gap(name: str) -> None:
    assert _has_real_gap(_parse(name))


@pytest.mark.parametrize("name", _skip_when_missing(["manual_transition_dissolve.kdenlive"]))
def test_transition_fixture_contains_real_dissolve(name: str) -> None:
    assert _has_dissolve_transition(_parse(name))


@pytest.mark.parametrize("name", _skip_when_missing(["manual_basic_effect.kdenlive"]))
def test_effect_fixture_contains_real_basic_effect(name: str) -> None:
    assert _has_basic_effect(_parse(name))
