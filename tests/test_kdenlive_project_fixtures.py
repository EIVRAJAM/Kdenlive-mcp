from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from kdenlive_mcp.adapters.kdenlive_xml import KdenliveProjectAdapter


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

ROUNDTRIP_GENERATED = "roundtrip_ai_generated.kdenlive"
ROUNDTRIP_RESAVED = "roundtrip_ai_resaved_by_kdenlive.kdenlive"
COMPOSITE_GENERATED = "composite_edit_ai_generated.kdenlive"

_ROUNDTRIP_SKIP_REASON = (
    f"{ROUNDTRIP_RESAVED} requires opening {ROUNDTRIP_GENERATED} in Kdenlive and "
    "saving it under that name; instructions in docs/KDENLIVE_PROJECT_FORMAT.md"
)


def _bin_chain_ids(root: ET.Element) -> set[str]:
    main_bin = root.find("playlist[@id='main_bin']")
    if main_bin is None:
        return set()
    return {
        entry.attrib["producer"]
        for entry in main_bin.findall("entry")
        if entry.attrib.get("producer", "").startswith("chain")
    }


def _chain_props(root: ET.Element) -> dict[str, dict[str, str]]:
    return {chain.attrib["id"]: _props(chain) for chain in root.findall("chain") if "id" in chain.attrib}


def _timeline_entry_chains(root: ET.Element, bin_ids: set[str]) -> list[tuple[str, str, str]]:
    chains = _chain_props(root)
    entries: list[tuple[str, str, str]] = []
    for playlist in root.findall("playlist"):
        if playlist.get("id") == "main_bin":
            continue
        for entry in playlist.findall("entry"):
            producer = entry.attrib.get("producer")
            if producer and producer in chains and producer not in bin_ids:
                props = chains[producer]
                entries.append((producer, props.get("kdenlive:id", ""), props.get("kdenlive:control_uuid", "")))
    return entries


def test_generated_project_timeline_chains_share_bin_control_uuid() -> None:
    root = _parse(ROUNDTRIP_GENERATED)
    bin_ids = _bin_chain_ids(root)
    chains = _chain_props(root)
    bin_media_uuids = {
        chains[chain_id].get("kdenlive:id"): chains[chain_id].get("kdenlive:control_uuid")
        for chain_id in bin_ids
    }

    for producer, media_id, control_uuid in _timeline_entry_chains(root, bin_ids):
        assert control_uuid == bin_media_uuids.get(media_id), (
            f"timeline chain {producer} control_uuid {control_uuid} does not match "
            f"bin chain for media {media_id} ({bin_media_uuids.get(media_id)})"
        )


def test_generated_project_timeline_entries_have_audio_index() -> None:
    root = _parse(ROUNDTRIP_GENERATED)

    for playlist in root.findall("playlist"):
        if playlist.get("id") == "main_bin":
            continue
        for entry in playlist.findall("entry"):
            assert _props(entry).get("kdenlive:audio_index") == "1"


def test_generated_project_uses_one_shared_timeline_chain_per_media() -> None:
    root = _parse(ROUNDTRIP_GENERATED)
    bin_ids = _bin_chain_ids(root)
    timeline_producers = {producer for producer, _, _ in _timeline_entry_chains(root, bin_ids)}
    chains = _chain_props(root)
    media_ids = {chains[producer].get("kdenlive:id") for producer in timeline_producers}

    for media_id in media_ids:
        matching = [producer for producer in timeline_producers if chains[producer].get("kdenlive:id") == media_id]
        assert len(matching) == 1, f"media {media_id} has {len(matching)} timeline chains: {matching}"


@pytest.mark.skipif(not (RECON_DIR / ROUNDTRIP_RESAVED).exists(), reason=_ROUNDTRIP_SKIP_REASON)
def test_resaved_project_timeline_chains_share_bin_control_uuid() -> None:
    root = _parse(ROUNDTRIP_RESAVED)
    bin_ids = _bin_chain_ids(root)
    chains = _chain_props(root)
    bin_media_uuids = {
        chains[chain_id].get("kdenlive:id"): chains[chain_id].get("kdenlive:control_uuid")
        for chain_id in bin_ids
    }

    for producer, media_id, control_uuid in _timeline_entry_chains(root, bin_ids):
        assert control_uuid == bin_media_uuids.get(media_id), (
            f"resaved timeline chain {producer} control_uuid {control_uuid} does not match "
            f"bin chain for media {media_id} ({bin_media_uuids.get(media_id)})"
        )


@pytest.mark.skipif(not (RECON_DIR / ROUNDTRIP_RESAVED).exists(), reason=_ROUNDTRIP_SKIP_REASON)
def test_roundtrip_resaved_project_is_well_formed_with_media_and_profile() -> None:
    root = _parse(ROUNDTRIP_RESAVED)

    assert root.tag == "mlt"
    assert root.attrib["producer"] == "main_bin"
    profile = root.find("profile")
    assert profile is not None
    assert profile.attrib["width"] == "1080"
    assert profile.attrib["height"] == "1920"
    assert profile.attrib["frame_rate_num"] == "30"
    assert profile.attrib["frame_rate_den"] == "1"
    assert profile.attrib["display_aspect_num"] == "9"
    assert profile.attrib["display_aspect_den"] == "16"

    for chain in root.findall("chain"):
        resource = _props(chain).get("resource")
        if resource and resource != "black":
            assert (RECON_DIR / resource).exists()


@pytest.mark.skipif(not (RECON_DIR / ROUNDTRIP_RESAVED).exists(), reason=_ROUNDTRIP_SKIP_REASON)
def test_roundtrip_resaved_project_inspects_cleanly() -> None:
    inspection = KdenliveProjectAdapter().inspect(RECON_DIR / ROUNDTRIP_RESAVED)
    active_sequence = next(
        sequence for sequence in inspection["sequences"] if sequence["id"] == inspection["active_sequence_id"]
    )

    assert inspection["document"]["profile"] == "vertical_hd_30"
    assert inspection["validation"]["missing_media_count"] == 0
    assert len(active_sequence["timeline_clips"]) > 0

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
    # Default track transitions (mix/qtblend) carry internal_added=237 and no
    # in/out attributes. A user clip transition (e.g. dissolve/wipe) is stored
    # with in/out attributes AND no internal_added=237.
    for transition in root.iter("transition"):
        props = _props(transition)
        has_in_out = transition.get("in") is not None and transition.get("out") is not None
        is_user = props.get("internal_added") != "237"
        if has_in_out and is_user:
            return True
        # Fallback: a non-default service without internal_added=237.
        if is_user and props.get("mlt_service") not in DEFAULT_TRANSITION_SERVICES:
            return True
    return False


def _has_basic_effect(root: ET.Element) -> bool:
    # A user effect on a clip is a <filter> nested inside a playlist <entry>.
    # Default per-track filters (volume/panner/audiolevel) live at the tractor
    # level, not inside entries.
    for playlist in root.findall("playlist"):
        for entry in playlist.findall("entry"):
            if entry.findall("filter"):
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


def _transition_element(in_out: bool, internal: str | None, service: str) -> ET.Element:
    attrs: dict[str, str] = {}
    if in_out:
        attrs["in"] = "00:00:01.000"
        attrs["out"] = "00:00:03.000"
    transition = ET.Element("transition", attrs)
    properties = [("mlt_service", service)]
    if internal is not None:
        properties.append(("internal_added", internal))
    for name, value in properties:
        prop = ET.SubElement(transition, "property")
        prop.set("name", name)
        prop.text = value
    return transition


def test_dissolve_detector_ignores_clip_transition_marked_internal() -> None:
    root = ET.Element("mlt")
    root.append(_transition_element(in_out=True, internal="237", service="mix"))

    assert _has_dissolve_transition(root) is False


def test_dissolve_detector_finds_user_transition_with_in_out() -> None:
    root = ET.Element("mlt")
    root.append(_transition_element(in_out=True, internal=None, service="composite"))

    assert _has_dissolve_transition(root) is True


def test_dissolve_detector_fallback_for_non_default_service_without_internal() -> None:
    root = ET.Element("mlt")
    root.append(_transition_element(in_out=False, internal=None, service="luma"))

    assert _has_dissolve_transition(root) is True


@pytest.mark.parametrize("name", [ROUNDTRIP_GENERATED, COMPOSITE_GENERATED])
def test_generated_projects_have_coherent_timeline_bin_references(name: str) -> None:
    root = _parse(name)
    bin_ids = _bin_chain_ids(root)
    chains = _chain_props(root)
    bin_media_uuids = {
        chains[chain_id].get("kdenlive:id"): chains[chain_id].get("kdenlive:control_uuid")
        for chain_id in bin_ids
    }
    timeline_producers: set[str] = set()
    for producer, media_id, control_uuid in _timeline_entry_chains(root, bin_ids):
        assert control_uuid == bin_media_uuids.get(media_id), (
            f"{producer} control_uuid {control_uuid} does not match bin for media {media_id}"
        )
        timeline_producers.add(producer)

    for media_id in {chains[producer].get("kdenlive:id") for producer in timeline_producers}:
        matching = [producer for producer in timeline_producers if chains[producer].get("kdenlive:id") == media_id]
        assert len(matching) == 1, f"media {media_id} has {len(matching)} timeline chains: {matching}"


@pytest.mark.parametrize("name", [ROUNDTRIP_GENERATED, COMPOSITE_GENERATED])
def test_generated_projects_timeline_entries_have_audio_index(name: str) -> None:
    root = _parse(name)

    for playlist in root.findall("playlist"):
        if playlist.get("id") == "main_bin":
            continue
        for entry in playlist.findall("entry"):
            assert _props(entry).get("kdenlive:audio_index") == "1"


def test_composite_edit_project_is_well_formed_with_media_and_profile() -> None:
    root = _parse(COMPOSITE_GENERATED)

    assert root.tag == "mlt"
    assert root.attrib["producer"] == "main_bin"
    profile = root.find("profile")
    assert profile is not None
    assert profile.attrib["width"] == "1080"
    assert profile.attrib["height"] == "1920"
    assert profile.attrib["frame_rate_num"] == "30"
    assert profile.attrib["frame_rate_den"] == "1"
    assert profile.attrib["display_aspect_num"] == "9"
    assert profile.attrib["display_aspect_den"] == "16"
    for chain in root.findall("chain"):
        resource = _props(chain).get("resource")
        if resource and resource != "black":
            assert (RECON_DIR / resource).exists()


def test_composite_edit_project_inspects_cleanly() -> None:
    inspection = KdenliveProjectAdapter().inspect(RECON_DIR / COMPOSITE_GENERATED)
    active_sequence = next(
        sequence for sequence in inspection["sequences"] if sequence["id"] == inspection["active_sequence_id"]
    )

    assert inspection["document"]["profile"] == "vertical_hd_30"
    assert inspection["validation"]["missing_media_count"] == 0
    assert len(active_sequence["timeline_clips"]) >= 4


def test_composite_edit_project_contains_trim_gap_and_split() -> None:
    root = _parse(COMPOSITE_GENERATED)

    assert _has_trimmed_clip(root)
    assert _has_real_gap(root)

    bin_ids = _bin_chain_ids(root)
    chains = _chain_props(root)
    timeline_clip_count = sum(
        1
        for playlist in root.findall("playlist")
        if playlist.get("id") != "main_bin"
        for entry in playlist.findall("entry")
        if entry.attrib.get("producer") in chains and entry.attrib.get("producer") not in bin_ids
    )
    assert timeline_clip_count >= 4  # split produces more entries than the base two-media timeline
