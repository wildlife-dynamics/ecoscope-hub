import json

from conftest import FakeResponse
from collect import CATALOG_URL, build, collect_workflow, fetch_catalog, find_version_path, main, resolve_catalog
from gh import API

SPEC = """
id: ndvi
metadata:
  name: NDVI Workflow
  description: Vegetation
  maintainers:
    - {name: Yun, email: y@x, role: owner}
  outputs:
    - name: NDVI Map
      type: map
      indicators: [{name: NDVI}]
"""

VOCAB = {"ndvi": "ndvi"}


def add_repo(session, repo="o/r", private=False, archived=False):
    session.add("GET", f"{API}/repos/{repo}", FakeResponse(200, {"full_name": repo, "private": private, "archived": archived, "default_branch": "main", "html_url": f"https://github.com/{repo}"}))


def add_spec(session, repo="o/r", text=SPEC):
    session.add("GET", f"{API}/repos/{repo}/contents/spec.yaml", FakeResponse(200, text=text))


def add_version(session, repo, ref, text="{MAJ: 1, MIN: 2, PATCH: 3}"):
    session.add("GET", f"{API}/repos/{repo}/contents/pkg-workflow/VERSION.yaml", lambda params, body: FakeResponse(200, text=text) if params == {"ref": ref} else FakeResponse(404, {}))


def add_tree(session, repo="o/r", ref="main", paths=("pkg-workflow/VERSION.yaml",)):
    session.add("GET", f"{API}/repos/{repo}/git/trees/{ref}", FakeResponse(200, {"tree": [{"path": p, "type": "blob"} for p in paths]}))


def add_ci(session, repo="o/r", conclusion="success"):
    session.add("GET", f"{API}/repos/{repo}/actions/workflows/test.yml/runs", FakeResponse(200, {"workflow_runs": [{"conclusion": conclusion, "html_url": "https://ci/1"}]}))


def add_issues(session, repo="o/r"):
    session.add(
        "GET",
        f"{API}/repos/{repo}/issues",
        FakeResponse(
            200,
            [
                {"number": 5, "title": "PR", "html_url": "u5", "labels": [], "created_at": "2026-01-01T00:00:00Z", "assignee": None, "pull_request": {}},
                {"number": 6, "title": "Bug", "html_url": "u6", "labels": [{"name": "bug"}], "created_at": "2026-01-02T00:00:00Z", "assignee": {"login": "yun"}},
            ],
        ),
    )


def add_epic(session, status="Ready"):
    session.add(
        "POST",
        f"{API}/graphql",
        FakeResponse(
            200,
            {
                "data": {
                    "repository": {
                        "issue": {
                            "title": "E",
                            "state": "OPEN",
                            "url": "https://github.com/o/r/issues/1",
                            "issueType": {"name": "Workflow"},
                            "subIssuesSummary": {"total": 0, "completed": 0},
                            "projectItems": {"nodes": [{"project": {"number": 9, "title": "Wildlife Dynamics", "url": "p"}, "fieldValues": {"nodes": [{"name": status, "field": {"name": "Status"}}]}}]},
                            "subIssues": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": []},
                        }
                    }
                }
            },
        ),
    )


def full_entry():
    return {"id": "r", "repo": "o/r", "epic": "https://github.com/o/r/issues/1"}


def test_fetch_catalog_maps_repo_to_version_path(session):
    session.add("GET", CATALOG_URL, FakeResponse(200, [{"url": "https://github.com/Wildlife-Dynamics/wt-ndvi", "version_file_path": "x-workflow/VERSION.yaml"}]))
    assert fetch_catalog(session) == {"wildlife-dynamics/wt-ndvi": "x-workflow/VERSION.yaml"}


def test_resolve_catalog_follows_renames(client, session):
    session.add("GET", f"{API}/repos/o/old", FakeResponse(200, {"full_name": "o/new"}))
    assert resolve_catalog(client, {"o/old": "p/VERSION.yaml"}) == {"o/new": "p/VERSION.yaml"}


def test_resolve_catalog_keeps_unknown_repo(client, session):
    session.add("GET", f"{API}/repos/o/gone", FakeResponse(404, {"message": "Not Found"}))
    assert resolve_catalog(client, {"o/gone": "p/VERSION.yaml"}) == {"o/gone": "p/VERSION.yaml"}


def test_find_version_path_picks_workflow_dir(client, session):
    add_tree(session, paths=("README.md", "pkg-workflow/VERSION.yaml", "other/VERSION.yaml"))
    assert find_version_path(client, "o/r", "main") == "pkg-workflow/VERSION.yaml"


def test_find_version_path_none_when_absent(client, session):
    add_tree(session, paths=("README.md",))
    assert find_version_path(client, "o/r", "main") is None


def test_collect_workflow_public_repo_full_record(client, session):
    add_epic(session)
    add_repo(session)
    add_spec(session)
    add_version(session, "o/r", "main")
    session.add("GET", f"{API}/repos/o/r/branches/ecoscope-web", FakeResponse(200, {"name": "ecoscope-web"}))
    add_version(session, "o/r", "ecoscope-web", "{MAJ: 1, MIN: 0, PATCH: 0}")
    add_ci(session)
    add_issues(session)
    record = collect_workflow(full_entry(), client, {"o/r": "pkg-workflow/VERSION.yaml"}, VOCAB)
    assert record["errors"] == []
    assert record["epic"]["status"] == "Ready"
    assert record["name"] == "NDVI Workflow"
    assert record["maintainers"] == [{"name": "Yun", "email": "y@x", "role": "owner"}]
    assert record["outputs"][0]["components"][0]["indicators"] == ["ndvi"]
    assert record["indicators"] == ["ndvi"]
    assert record["desktop_version"] == "1.2.3"
    assert record["web_version"] == "1.0.0"
    assert record["ci_status"] == "success"
    assert record["ci_url"] == "https://ci/1"
    assert record["open_issue_count"] == 1
    assert record["issues"] == [{"number": 6, "title": "Bug", "url": "u6", "labels": ["bug"], "created_at": "2026-01-02T00:00:00Z", "assignee": "yun"}]
    assert record["metadata_missing"] is False and record["spec_missing"] is False
    assert record["metadata_source"] == "main"


def test_collect_workflow_metadata_falls_back_to_web_branch(client, session):
    add_epic(session)
    add_repo(session)
    session.add("GET", f"{API}/repos/o/r/branches/ecoscope-web", FakeResponse(200, {"name": "ecoscope-web"}))
    session.add("GET", f"{API}/repos/o/r/contents/spec.yaml", lambda params, body: FakeResponse(200, text=SPEC) if params == {"ref": "ecoscope-web"} else FakeResponse(200, text="id: x\n"))
    add_ci(session)
    add_issues(session)
    record = collect_workflow(full_entry(), client, {}, VOCAB)
    assert record["metadata_missing"] is False
    assert record["metadata_source"] == "ecoscope-web"
    assert record["name"] == "NDVI Workflow"


def test_collect_workflow_metadata_prefers_default_branch(client, session):
    add_epic(session)
    add_repo(session)
    add_spec(session)
    session.add("GET", f"{API}/repos/o/r/branches/ecoscope-web", FakeResponse(200, {"name": "ecoscope-web"}))
    add_ci(session)
    add_issues(session)
    record = collect_workflow(full_entry(), client, {}, VOCAB)
    assert record["metadata_missing"] is False
    assert record["metadata_source"] == "main"
    assert record["name"] == "NDVI Workflow"


def test_collect_workflow_resolves_renamed_repo_alias(client, session):
    add_epic(session)
    session.add("GET", f"{API}/repos/o/alias", FakeResponse(200, {"full_name": "o/r", "private": False, "archived": False, "default_branch": "main", "html_url": "https://github.com/o/r"}))
    add_spec(session, repo="o/alias")
    add_version(session, "o/alias", "main")
    add_ci(session, repo="o/alias")
    add_issues(session, repo="o/alias")
    entry = {"id": "r", "repo": "o/alias", "epic": "https://github.com/o/r/issues/1"}
    record = collect_workflow(entry, client, {"o/r": "pkg-workflow/VERSION.yaml"}, VOCAB)
    assert record["repo"] == "o/r"
    assert record["desktop_version"] == "1.2.3"


def test_collect_workflow_private_repo_is_excluded(client, session):
    add_epic(session)
    add_repo(session, private=True)
    record = collect_workflow(full_entry(), client, {"o/r": "pkg-workflow/VERSION.yaml"}, VOCAB)
    assert record is None
    assert not any(c["url"].endswith("/contents/spec.yaml") for c in session.calls)
    assert not any("VERSION" in c["url"] for c in session.calls)
    assert not any(c["url"].endswith("/branches/ecoscope-web") for c in session.calls)
    assert not any(c["url"].endswith("/issues") for c in session.calls)


def test_collect_workflow_not_in_catalog_and_no_web_branch(client, session):
    add_epic(session)
    add_repo(session)
    add_spec(session)
    add_tree(session)
    add_ci(session)
    add_issues(session)
    record = collect_workflow(full_entry(), client, {}, VOCAB)
    assert record["desktop_version"] is None
    assert record["web_version"] is None
    assert record["errors"] == []


def test_collect_workflow_web_branch_without_catalog_uses_tree_path(client, session):
    add_epic(session)
    add_repo(session)
    add_spec(session)
    add_tree(session, ref="ecoscope-web")
    session.add("GET", f"{API}/repos/o/r/branches/ecoscope-web", FakeResponse(200, {"name": "ecoscope-web"}))
    add_version(session, "o/r", "ecoscope-web", "{MAJ: 0, MIN: 9, PATCH: 0}")
    add_ci(session)
    add_issues(session)
    record = collect_workflow(full_entry(), client, {}, VOCAB)
    assert record["web_version"] == "0.9.0"
    assert record["desktop_version"] is None


def test_collect_workflow_missing_metadata_and_spec_flags(client, session):
    add_epic(session)
    add_repo(session)
    add_spec(session, text="id: x\n")
    add_ci(session)
    add_issues(session)
    record = collect_workflow(full_entry(), client, {}, VOCAB)
    assert record["metadata_missing"] is True and record["spec_missing"] is False
    assert record["name"] == "r"
    assert record["metadata_source"] is None

    session2 = type(session)()
    client2 = type(client)(token="t", session=session2)
    add_epic(session2)
    add_repo(session2)
    add_ci(session2)
    add_issues(session2)
    record = collect_workflow(full_entry(), client2, {}, VOCAB)
    assert record["spec_missing"] is True and record["metadata_missing"] is True
    assert record["metadata_source"] is None


def test_collect_workflow_repo_404_records_error_but_keeps_epic(client, session):
    add_epic(session)
    record = collect_workflow(full_entry(), client, {}, VOCAB)
    assert record["epic"]["status"] == "Ready"
    assert any("repo not found" in e for e in record["errors"])


def test_collect_workflow_epic_failure_is_isolated(client, session):
    add_repo(session)
    add_spec(session)
    add_ci(session)
    add_issues(session)
    session.add("POST", f"{API}/graphql", FakeResponse(200, {"errors": [{"message": "nope"}]}))
    record = collect_workflow(full_entry(), client, {}, VOCAB)
    assert record["epic"] is None
    assert any("nope" in e for e in record["errors"])
    assert record["name"] == "NDVI Workflow"


def test_collect_workflow_no_ci_workflow_file(client, session):
    add_epic(session)
    add_repo(session)
    add_spec(session)
    add_issues(session)
    record = collect_workflow(full_entry(), client, {}, VOCAB)
    assert record["ci_status"] is None and record["ci_url"] is None
    assert record["errors"] == []


def test_collect_workflow_entry_without_repo(client, session):
    add_epic(session)
    record = collect_workflow({"id": "planned", "repo": None, "epic": "https://github.com/o/r/issues/1"}, client, {}, VOCAB)
    assert record["repo"] is None
    assert record["epic"]["title"] == "E"
    assert record["spec_missing"] is True
    assert record["errors"] == []


def test_collect_workflow_issues_bad_label_is_isolated(client, session):
    add_epic(session)
    add_repo(session)
    add_spec(session)
    add_ci(session)
    session.add(
        "GET",
        f"{API}/repos/o/r/issues",
        FakeResponse(
            200,
            [{"number": 7, "title": "Bad", "html_url": "u7", "labels": ["bug"], "created_at": "2026-01-03T00:00:00Z", "assignee": None}],
        ),
    )
    record = collect_workflow(full_entry(), client, {}, VOCAB)
    assert record["issues"] == []
    assert record["open_issue_count"] == 0
    assert record["name"] == "NDVI Workflow"
    assert any(e.startswith("issues:") for e in record["errors"])


def test_build_records_unexpected_exception(client, session, monkeypatch):
    import collect as mod

    monkeypatch.setattr(mod, "collect_workflow", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    snapshot = build([full_entry()], client, {}, VOCAB, [])
    assert [w["id"] for w in snapshot["workflows"]] == ["r"]
    assert snapshot["workflows"][0]["errors"] == ["unexpected: RuntimeError('boom')"]


def test_build_isolates_failures_and_stamps_time(client, session):
    add_epic(session)
    add_repo(session)
    add_spec(session)
    add_ci(session)
    add_issues(session)
    entries = [full_entry(), {"id": "gone", "repo": "o/gone", "epic": None}]
    snapshot = build(entries, client, {}, VOCAB, [{"repo": "o/new"}])
    assert snapshot["generated_at"].endswith("Z")
    assert [w["id"] for w in snapshot["workflows"]] == ["r", "gone"]
    assert snapshot["workflows"][1]["errors"]
    assert snapshot["unregistered"] == [{"repo": "o/new"}]
    assert snapshot["warnings"] == []


def test_build_skips_private_records(client, session):
    add_epic(session)
    add_repo(session, private=True)
    snapshot = build([full_entry()], client, {}, VOCAB, [])
    assert snapshot["workflows"] == []


def test_main_writes_json_and_honours_only(tmp_path, session, monkeypatch):
    import collect as mod

    real = mod.GitHubClient
    monkeypatch.setattr(mod, "GitHubClient", lambda: real(token="t", session=session))
    session.add("GET", CATALOG_URL, FakeResponse(200, []))
    add_epic(session)
    add_repo(session)
    add_spec(session)
    add_ci(session)
    add_issues(session)
    registry = tmp_path / "registry.yaml"
    registry.write_text("workflows:\n  - id: r\n    repo: o/r\n    epic: https://github.com/o/r/issues/1\n  - id: other\n    repo: o/other\n")
    indicators = tmp_path / "indicators.yaml"
    indicators.write_text("indicators:\n  ndvi:\n    label: NDVI\n")
    unregistered = tmp_path / "unreg.json"
    unregistered.write_text('[{"repo": "o/new"}]')
    out = tmp_path / "build" / "data.json"
    code = main(["--registry", str(registry), "--indicators", str(indicators), "--out", str(out), "--only", "r", "--unregistered", str(unregistered)])
    assert code == 0
    data = json.loads(out.read_text())
    assert [w["id"] for w in data["workflows"]] == ["r"]
    assert data["unregistered"][0]["repo"] == "o/new"


def test_main_missing_unregistered_file_is_tolerated(tmp_path, session, monkeypatch):
    import collect as mod

    real = mod.GitHubClient
    monkeypatch.setattr(mod, "GitHubClient", lambda: real(token="t", session=session))
    session.add("GET", CATALOG_URL, FakeResponse(200, []))
    add_epic(session)
    add_repo(session)
    add_spec(session)
    add_ci(session)
    add_issues(session)
    registry = tmp_path / "registry.yaml"
    registry.write_text("workflows:\n  - id: r\n    repo: o/r\n    epic: https://github.com/o/r/issues/1\n")
    indicators = tmp_path / "indicators.yaml"
    indicators.write_text("indicators:\n  ndvi:\n    label: NDVI\n")
    out = tmp_path / "build" / "data.json"
    code = main(["--registry", str(registry), "--indicators", str(indicators), "--out", str(out), "--unregistered", str(tmp_path / "missing.json")])
    assert code == 0
    data = json.loads(out.read_text())
    assert data["unregistered"] == []


def test_main_records_catalog_warning(tmp_path, session, monkeypatch):
    import collect as mod

    real = mod.GitHubClient
    monkeypatch.setattr(mod, "GitHubClient", lambda: real(token="t", session=session))
    session.add("GET", CATALOG_URL, FakeResponse(503, {}))
    add_epic(session)
    add_repo(session)
    add_spec(session)
    add_ci(session)
    add_issues(session)
    registry = tmp_path / "registry.yaml"
    registry.write_text("workflows:\n  - id: r\n    repo: o/r\n    epic: https://github.com/o/r/issues/1\n")
    indicators = tmp_path / "indicators.yaml"
    indicators.write_text("indicators:\n  ndvi:\n    label: NDVI\n")
    out = tmp_path / "build" / "data.json"
    code = main(["--registry", str(registry), "--indicators", str(indicators), "--out", str(out)])
    assert code == 0
    data = json.loads(out.read_text())
    assert data["warnings"] == ["Desktop catalog unavailable: catalog fetch failed: 503"]


def test_main_fails_on_invalid_registry(tmp_path, capsys):
    registry = tmp_path / "registry.yaml"
    registry.write_text("workflows:\n  - id: a\n")
    code = main(["--registry", str(registry), "--indicators", str(registry), "--out", str(tmp_path / "d.json")])
    assert code == 2
    assert "repo or epic" in capsys.readouterr().err
