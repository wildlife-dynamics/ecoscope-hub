import argparse
import json
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import yaml

from epic import fetch_epic
from gh import GitHubClient, GitHubError, NotFound
from metadata import RegistryError, load_indicators, load_registry, normalize_outputs, parse_version

CATALOG_URL = "https://storage.googleapis.com/ecoscope-io-storage-public/ecoscope-desktop/hardcoded-template-catalog/workflow_templates.json"
WEB_BRANCH = "ecoscope-web"
HERE = Path(__file__).parent


def fetch_catalog(session):
    response = session.request("GET", CATALOG_URL, timeout=30)
    if response.status_code >= 400:
        raise GitHubError(f"catalog fetch failed: {response.status_code}")
    catalog = {}
    for item in response.json():
        url = str(item.get("url") or "").rstrip("/")
        prefix = "https://github.com/"
        if url.lower().startswith(prefix) and item.get("version_file_path"):
            catalog[url[len(prefix):].lower()] = item["version_file_path"]
    return catalog


def resolve_catalog(client, catalog):
    resolved = {}
    for key, path in catalog.items():
        try:
            info = client.get(f"/repos/{key}")
            resolved[info["full_name"].lower()] = path
        except NotFound:
            resolved[key] = path
        except GitHubError:
            resolved[key] = path
    return resolved


def find_version_path(client, repo, ref):
    tree = client.get(f"/repos/{repo}/git/trees/{ref}", params={"recursive": "1"})
    for node in tree.get("tree", []):
        path = node.get("path", "")
        parts = path.split("/")
        if node.get("type") == "blob" and len(parts) == 2 and parts[0].endswith("-workflow") and parts[1] == "VERSION.yaml":
            return path
    return None


def _read_version(client, repo, ref, path):
    return parse_version(client.get_text(repo, path, ref))


def _branch_exists(client, repo, branch):
    try:
        client.get(f"/repos/{repo}/branches/{branch}")
        return True
    except NotFound:
        return False


def _read_metadata(client, repo, ref):
    try:
        spec = yaml.safe_load(client.get_text(repo, "spec.yaml", ref)) or {}
    except NotFound:
        return None, [], False
    meta = spec.get("metadata") if isinstance(spec, dict) else None
    requirements = spec.get("requirements") if isinstance(spec, dict) else None
    requirements = requirements if isinstance(requirements, list) else []
    task_libraries = [
        {"name": str(r.get("name") or ""), "version": str(r.get("version") or ""), "channel": str(r.get("channel") or "")}
        for r in requirements
        if isinstance(r, dict)
    ]
    return meta, task_libraries, True


def _read_wt_compiler_version(client, repo, ref):
    try:
        text = client.get_text(repo, "pixi.toml", ref)
    except NotFound:
        return None
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return None
    deps = data.get("dependencies") if isinstance(data, dict) else None
    version = deps.get("wt-compiler") if isinstance(deps, dict) else None
    return version if isinstance(version, str) else None


CI_WORKFLOW_FILES = ("test.yml", "ci.yml")


def _ci(client, repo, branch):
    for workflow_file in CI_WORKFLOW_FILES:
        try:
            runs = client.get(f"/repos/{repo}/actions/workflows/{workflow_file}/runs", params={"branch": branch, "per_page": 1})
        except NotFound:
            continue
        latest = (runs.get("workflow_runs") or [None])[0]
        if not latest:
            return None, None
        return latest.get("conclusion"), latest.get("html_url")
    return None, None


def _issues(client, repo):
    items = client.paginate(f"/repos/{repo}/issues", params={"state": "open"})
    return [
        {
            "number": i["number"],
            "title": i.get("title"),
            "url": i.get("html_url"),
            "labels": [lb["name"] for lb in i.get("labels") or []],
            "created_at": i.get("created_at"),
            "assignee": (i.get("assignee") or {}).get("login"),
        }
        for i in items
        if "pull_request" not in i and (i.get("type") or {}).get("name") != "Workflow"
    ]


def _empty_record(entry):
    return {
        "id": entry["id"],
        "repo": entry.get("repo"),
        "epic": None,
        "archived": None,
        "name": entry["id"],
        "description": "",
        "maintainers": [],
        "outputs": [],
        "indicators": [],
        "unknown_indicators": [],
        "metadata_missing": True,
        "spec_missing": True,
        "metadata_source": None,
        "task_libraries": [],
        "wt_compiler_version": None,
        "desktop_version": None,
        "web_version": None,
        "ci_status": None,
        "ci_url": None,
        "open_issue_count": 0,
        "issues": [],
        "errors": [],
    }


def collect_workflow(entry, client, catalog, vocab):
    record = _empty_record(entry)
    errors = record["errors"]

    if entry.get("epic"):
        try:
            record["epic"], epic_errors = fetch_epic(client, entry["epic"])
            errors.extend(epic_errors)
        except Exception as e:  # noqa: BLE001 - keep other fields even if the epic lookup breaks
            errors.append(f"epic: {e}")

    repo = entry.get("repo")
    if not repo:
        return record

    try:
        info = client.get(f"/repos/{repo}")
    except NotFound:
        errors.append(f"repo not found: {repo}")
        return record
    except Exception as e:  # noqa: BLE001
        errors.append(f"repo: {e}")
        return record
    if info.get("private"):
        print(f"warning: {entry['id']}: repo {repo} is private, excluded", file=sys.stderr)
        return None
    record["repo"] = info.get("full_name") or repo
    record["archived"] = bool(info.get("archived"))
    branch = info.get("default_branch") or "main"
    web_exists = _branch_exists(client, repo, WEB_BRANCH)

    meta = None
    task_libraries = []
    try:
        meta, task_libraries, spec_found = _read_metadata(client, repo, branch)
    except Exception as e:  # noqa: BLE001
        errors.append(f"spec.yaml: {e}")
        spec_found = False
    record["spec_missing"] = not spec_found
    record["metadata_source"] = branch if isinstance(meta, dict) else None

    if not isinstance(meta, dict) and web_exists:
        try:
            web_meta, web_task_libraries, _ = _read_metadata(client, repo, WEB_BRANCH)
        except Exception as e:  # noqa: BLE001
            errors.append(f"spec.yaml@{WEB_BRANCH}: {e}")
            web_meta, web_task_libraries = None, []
        if isinstance(web_meta, dict):
            meta = web_meta
            task_libraries = web_task_libraries
            record["metadata_source"] = WEB_BRANCH

    record["task_libraries"] = task_libraries

    if isinstance(meta, dict):
        record["metadata_missing"] = False
        record["name"] = str(meta.get("name") or entry["id"])
        record["description"] = str(meta.get("description") or "")
        record["maintainers"] = [m for m in meta.get("maintainers") or [] if isinstance(m, dict)]
        record["outputs"], record["indicators"], record["unknown_indicators"] = normalize_outputs(meta, record["name"], vocab)

    try:
        record["wt_compiler_version"] = _read_wt_compiler_version(client, repo, branch)
    except Exception as e:  # noqa: BLE001
        errors.append(f"pixi.toml: {e}")

    canonical = (info.get("full_name") or repo).lower()
    version_path = catalog.get(canonical)
    try:
        if not version_path:
            version_path = find_version_path(client, repo, branch)
    except NotFound:
        version_path = None
    except Exception as e:  # noqa: BLE001
        errors.append(f"version: {e}")
        version_path = None
    try:
        if version_path:
            record["desktop_version"] = _read_version(client, repo, branch, version_path)
        if web_exists:
            path = version_path or find_version_path(client, repo, WEB_BRANCH)
            if path:
                record["web_version"] = _read_version(client, repo, WEB_BRANCH, path)
    except Exception as e:  # noqa: BLE001
        errors.append(f"version: {e}")

    try:
        record["ci_status"], record["ci_url"] = _ci(client, repo, branch)
    except Exception as e:  # noqa: BLE001
        errors.append(f"ci: {e}")

    try:
        record["issues"] = _issues(client, repo)
        record["open_issue_count"] = len(record["issues"])
    except Exception as e:  # noqa: BLE001
        errors.append(f"issues: {e}")

    return record


def build(entries, client, catalog, vocab, unregistered, warnings=None):
    workflows = []
    for entry in entries:
        try:
            record = collect_workflow(entry, client, catalog, vocab)
            if record is not None:
                workflows.append(record)
        except Exception as e:  # noqa: BLE001 - one bad repo must not blank the page
            record = _empty_record(entry)
            record["errors"].append(f"unexpected: {e!r}")
            workflows.append(record)
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "warnings": list(warnings or []),
        "unregistered": list(unregistered or []),
        "workflows": workflows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Collect the workflow monitor snapshot.")
    parser.add_argument("--registry", default=str(HERE / "registry.yaml"))
    parser.add_argument("--indicators", default=str(HERE / "indicators.yaml"))
    parser.add_argument("--out", default=str(HERE / "build" / "data.json"))
    parser.add_argument("--only", action="append", default=[], help="workflow id to collect (repeatable)")
    parser.add_argument("--unregistered", help="JSON file produced by discover.py --json")
    args = parser.parse_args(argv)

    try:
        entries = load_registry(args.registry)
        vocab = load_indicators(args.indicators)
        unregistered = []
        if args.unregistered:
            unregistered_path = Path(args.unregistered)
            if unregistered_path.exists():
                unregistered = json.loads(unregistered_path.read_text())
            else:
                print(f"warning: unregistered file not found: {unregistered_path}", file=sys.stderr)
    except (RegistryError, OSError, yaml.YAMLError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.only:
        entries = [e for e in entries if e["id"] in set(args.only)]

    client = GitHubClient()
    warnings = []
    try:
        catalog = fetch_catalog(client.session)
        catalog = resolve_catalog(client, catalog)
    except Exception as e:  # noqa: BLE001
        print(f"warning: catalog unavailable ({e}); desktop versions will be empty", file=sys.stderr)
        catalog = {}
        warnings.append(f"Desktop catalog unavailable: {e}")

    snapshot = build(entries, client, catalog, vocab, unregistered, warnings=warnings)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, indent=2, sort_keys=False) + "\n")
    errors = sum(len(w["errors"]) for w in snapshot["workflows"])
    print(f"wrote {out} ({len(snapshot['workflows'])} workflows, {errors} errors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
