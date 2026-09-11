import pytest
import yaml

from metadata import RegistryError, load_registry, load_indicators, normalize_indicators, normalize_outputs, parse_version


def write_registry(tmp_path, workflows):
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump({"workflows": workflows}))
    return path


def test_load_registry_returns_normalised_entries(tmp_path):
    path = write_registry(
        tmp_path,
        [
            {"id": "a", "repo": "org/a", "epic": "https://github.com/org/a/issues/1"},
            {"id": "b", "epic": "https://github.com/org/b/issues/2"},
            {"id": "c", "repo": "org/c"},
        ],
    )
    entries = load_registry(path)
    assert entries == [
        {"id": "a", "repo": "org/a", "epic": "https://github.com/org/a/issues/1"},
        {"id": "b", "repo": None, "epic": "https://github.com/org/b/issues/2"},
        {"id": "c", "repo": "org/c", "epic": None},
    ]


def test_load_registry_rejects_duplicate_id(tmp_path):
    path = write_registry(tmp_path, [{"id": "a", "repo": "org/a"}, {"id": "a", "repo": "org/b"}])
    with pytest.raises(RegistryError, match="duplicate id"):
        load_registry(path)


def test_load_registry_rejects_repo_used_by_two_ids(tmp_path):
    path = write_registry(tmp_path, [{"id": "a", "repo": "org/shared"}, {"id": "b", "repo": "Org/Shared"}])
    with pytest.raises(RegistryError, match="used by both"):
        load_registry(path)


def test_load_registry_rejects_bad_epic_url(tmp_path):
    path = write_registry(tmp_path, [{"id": "a", "repo": "org/a", "epic": "https://github.com/org/a/pull/1"}])
    with pytest.raises(RegistryError, match="epic"):
        load_registry(path)


def test_load_registry_rejects_entry_without_repo_or_epic(tmp_path):
    path = write_registry(tmp_path, [{"id": "a"}])
    with pytest.raises(RegistryError, match="repo or epic"):
        load_registry(path)


def test_load_registry_rejects_missing_id(tmp_path):
    path = write_registry(tmp_path, [{"repo": "org/a"}])
    with pytest.raises(RegistryError, match="id"):
        load_registry(path)


@pytest.fixture
def vocab(tmp_path):
    path = tmp_path / "indicators.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "indicators": {
                    "ndvi": {"label": "NDVI", "aliases": ["vegetation index"]},
                    "patrol-distance": {"label": "Patrol distance", "aliases": ["distance patrolled"]},
                }
            }
        )
    )
    return load_indicators(path)


def test_load_indicators_maps_id_label_and_aliases(vocab):
    assert vocab["ndvi"] == "ndvi"
    assert vocab["vegetation index"] == "ndvi"
    assert vocab["patrol distance"] == "patrol-distance"


def test_normalize_indicators_handles_strings_dicts_case_and_unknowns(vocab):
    canon, unknown = normalize_indicators(["NDVI", {"name": "Vegetation Index"}, "ndvi", "elephant density"], vocab)
    assert canon == ["ndvi"]
    assert unknown == ["elephant density"]


def test_normalize_outputs_flat_shape_preserved_in_order(vocab):
    meta = {
        "outputs": [
            {"name": "NDVI Dashboard", "type": "dashboard", "description": "d", "indicators": [{"name": "NDVI"}]},
            {"name": "NDVI Map", "type": "map", "description": "m", "indicators": [{"name": "NDVI"}]},
            {"name": "NDVI Trend", "type": "plot", "description": "t", "indicators": [{"name": "vegetation index"}]},
            {"name": "NDVI Data", "type": "file", "description": "", "indicators": []},
        ]
    }
    outputs, indicators, unknown = normalize_outputs(meta, "X", vocab)
    assert outputs == [
        {"name": "NDVI Dashboard", "type": "dashboard", "description": "d", "indicators": ["ndvi"]},
        {"name": "NDVI Map", "type": "map", "description": "m", "indicators": ["ndvi"]},
        {"name": "NDVI Trend", "type": "plot", "description": "t", "indicators": ["ndvi"]},
        {"name": "NDVI Data", "type": "file", "description": "", "indicators": []},
    ]
    assert indicators == ["ndvi"]
    assert unknown == []


def test_normalize_outputs_nested_components_flattened_after_parent(vocab):
    meta = {
        "outputs": [
            {
                "name": "NDVI Dashboard",
                "type": "dashboard",
                "description": "d",
                "components": [
                    {"name": "NDVI Map", "type": "map", "description": "m", "indicators": ["NDVI"]},
                    {"name": "Trend", "type": "plot", "indicators": [{"name": "vegetation index"}]},
                ],
            },
            {"name": "NDVI Data", "type": "file"},
        ]
    }
    outputs, indicators, unknown = normalize_outputs(meta, "X", vocab)
    assert outputs == [
        {"name": "NDVI Dashboard", "type": "dashboard", "description": "d", "indicators": []},
        {"name": "NDVI Map", "type": "map", "description": "m", "indicators": ["ndvi"]},
        {"name": "Trend", "type": "plot", "description": "", "indicators": ["ndvi"]},
        {"name": "NDVI Data", "type": "file", "description": "", "indicators": []},
    ]
    assert indicators == ["ndvi"]
    assert unknown == []


def test_normalize_outputs_unknown_types_are_kept_and_flagged(vocab):
    meta = {"outputs": [{"name": "Thing", "type": "widget", "indicators": ["mystery"]}]}
    outputs, indicators, unknown = normalize_outputs(meta, "X", vocab)
    assert outputs[0]["type"] == "widget"
    assert unknown == ["mystery"]


def test_normalize_outputs_none_metadata(vocab):
    assert normalize_outputs(None, "X", vocab) == ([], [], [])


def test_parse_version():
    assert parse_version("{MAJ: 1, MIN: 0, PATCH: 1}\n") == "1.0.1"
    assert parse_version("MAJ: 2\nMIN: 3\nPATCH: 4\n") == "2.3.4"
    assert parse_version("nonsense") is None
    assert parse_version("") is None
