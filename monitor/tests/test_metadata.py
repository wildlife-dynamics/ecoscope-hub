import pytest
import yaml

from metadata import RegistryError, load_registry


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
