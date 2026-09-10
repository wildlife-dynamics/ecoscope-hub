import json

import yaml

from conftest import FakeResponse
from discover import add_stubs, diff, has_spec, list_org_repos, main
from gh import API


def test_list_org_repos_skips_archived(client, session):
    session.add("GET", f"{API}/orgs/wd/repos", FakeResponse(200, [
        {"full_name": "wd/a", "private": False, "archived": False},
        {"full_name": "wd/b", "private": True, "archived": True},
    ]))
    assert list_org_repos(client, "wd") == [{"repo": "wd/a", "visibility": "public"}]
    assert session.calls[0]["params"]["type"] == "all"


def test_has_spec(client, session):
    session.add("GET", f"{API}/repos/wd/a/contents/spec.yaml", FakeResponse(200, {"name": "spec.yaml"}))
    assert has_spec(client, "wd/a") is True
    assert has_spec(client, "wd/b") is False


def test_diff_groups():
    entries = [{"id": "a", "repo": "wd/a", "epic": None}, {"id": "z", "repo": "wd/z", "epic": None}, {"id": "noepicnorepo", "repo": None, "epic": "https://github.com/wd/x/issues/1"}]
    org = [{"repo": "wd/a", "visibility": "public", "archived": False}, {"repo": "wd/b", "visibility": "private", "archived": False}, {"repo": "wd/c", "visibility": "public", "archived": False}]
    result = diff(entries, org, {"wd/a": True, "wd/b": True, "wd/c": False})
    assert result["missing"] == [{"repo": "wd/b", "visibility": "private"}]
    assert result["gone"] == ["z"]
    assert result["not_workflow"] == ["wd/c"]


def test_diff_is_case_insensitive_on_repo():
    entries = [{"id": "a", "repo": "WD/A", "epic": None}]
    org = [{"repo": "wd/a", "visibility": "public", "archived": False}]
    result = diff(entries, org, {"wd/a": True})
    assert result["missing"] == [] and result["gone"] == []


def test_add_stubs_appends_and_preserves_existing(tmp_path):
    path = tmp_path / "registry.yaml"
    path.write_text("# keep me\nworkflows:\n  - id: a\n    repo: wd/a\n")
    n = add_stubs(path, [{"repo": "wd/new-thing", "visibility": "public"}])
    assert n == 1
    text = path.read_text()
    assert text.startswith("# keep me")
    data = yaml.safe_load(text)
    assert data["workflows"] == [{"id": "a", "repo": "wd/a"}, {"id": "new-thing", "repo": "wd/new-thing"}]


def test_main_json_prints_missing(client, session, tmp_path, capsys, monkeypatch):
    import discover as mod

    real = mod.GitHubClient
    monkeypatch.setattr(mod, "GitHubClient", lambda: real(token="t", session=session))
    session.add("GET", f"{API}/orgs/wd/repos", FakeResponse(200, [{"full_name": "wd/b", "private": False, "archived": False}]))
    session.add("GET", f"{API}/repos/wd/b/contents/spec.yaml", FakeResponse(200, {}))
    registry = tmp_path / "registry.yaml"
    registry.write_text("workflows:\n  - id: a\n    repo: wd/a\n")
    assert main(["--registry", str(registry), "--org", "wd", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == [{"repo": "wd/b", "visibility": "public"}]


def test_main_warns_and_continues_on_unreadable_repo(client, session, tmp_path, capsys, monkeypatch):
    import discover as mod

    real = mod.GitHubClient
    monkeypatch.setattr(mod, "GitHubClient", lambda: real(token="t", session=session))
    session.add("GET", f"{API}/orgs/wd/repos", FakeResponse(200, [{"full_name": "wd/a", "private": False, "archived": False}, {"full_name": "wd/b", "private": False, "archived": False}]))
    session.add("GET", f"{API}/repos/wd/a/contents/spec.yaml", FakeResponse(403, {"message": "forbidden"}))
    session.add("GET", f"{API}/repos/wd/b/contents/spec.yaml", FakeResponse(200, {}))
    registry = tmp_path / "registry.yaml"
    registry.write_text("workflows: []\n")
    assert main(["--registry", str(registry), "--org", "wd", "--json"]) == 0
    out, err = capsys.readouterr()
    assert json.loads(out) == [{"repo": "wd/b", "visibility": "public"}]
    assert "warning: could not read" in err


def test_main_json_prints_empty_list_when_org_listing_fails(client, session, tmp_path, capsys, monkeypatch):
    import discover as mod

    real = mod.GitHubClient
    monkeypatch.setattr(mod, "GitHubClient", lambda: real(token="t", session=session))
    session.add("GET", f"{API}/orgs/wd/repos", FakeResponse(500, {"message": "boom"}))
    registry = tmp_path / "registry.yaml"
    registry.write_text("workflows:\n  - id: a\n    repo: wd/a\n")
    assert main(["--registry", str(registry), "--org", "wd", "--json"]) == 0
    out, err = capsys.readouterr()
    assert out.strip() == "[]"
    assert "could not list org repos" in err


def test_add_stubs_handles_empty_flow_list(tmp_path):
    path = tmp_path / "registry.yaml"
    path.write_text("workflows: []\n")
    n = add_stubs(path, [{"repo": "wd/new-thing", "visibility": "public"}])
    assert n == 1
    data = yaml.safe_load(path.read_text())
    assert data["workflows"] == [{"id": "new-thing", "repo": "wd/new-thing"}]


def test_add_stubs_rolls_back_on_unparseable_result(tmp_path):
    from metadata import RegistryError

    path = tmp_path / "registry.yaml"
    path.write_text("workflows: {a: 1}\n")
    try:
        add_stubs(path, [{"repo": "wd/new", "visibility": "public"}])
        assert False, "should raise RegistryError"
    except RegistryError:
        pass
    assert path.read_text() == "workflows: {a: 1}\n"
