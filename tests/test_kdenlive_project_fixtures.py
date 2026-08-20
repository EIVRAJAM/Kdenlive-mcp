from pathlib import Path
import xml.etree.ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[1]
RECON_DIR = REPO_ROOT / "examples" / "recon"


REFERENCE_PROJECTS = [
    "manual_empty_vertical.kdenlive",
    "manual_bin_only.kdenlive",
    "manual_two_clips_timeline.kdenlive",
    "manual_trim_marker.kdenlive",
]


def _props(element: ET.Element) -> dict[str, str]:
    return {
        prop.attrib["name"]: prop.text or ""
        for prop in element.findall("property")
        if "name" in prop.attrib
    }


def _parse(name: str) -> ET.Element:
    return ET.parse(RECON_DIR / name).getroot()


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
