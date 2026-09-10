import argparse
import json
import re
import sys
from pathlib import Path

import yaml

from gh import GitHubClient, GitHubError, NotFound
from metadata import RegistryError, load_registry

HERE = Path(__file__).parent


def list_org_repos(client, org):
    repos = client.paginate(f"/orgs/{org}/repos", params={"type": "all"})
    return [
        {"repo": r["full_name"], "visibility": "private" if r.get("private") else "public"}
        for r in repos
        if not r.get("archived")
    ]


def has_spec(client, repo):
    try:
        client.get(f"/repos/{repo}/contents/spec.yaml")
        return True
    except NotFound:
        return False


def diff(entries, org_repos, spec_flags):
    registered = {e["repo"].lower(): e["id"] for e in entries if e.get("repo")}
    org_by_name = {r["repo"].lower(): r for r in org_repos}
    missing = [
        {"repo": r["repo"], "visibility": r["visibility"]}
        for r in org_repos
        if spec_flags.get(r["repo"], False) and r["repo"].lower() not in registered
    ]
    gone = [wid for name, wid in registered.items() if name not in org_by_name]
    not_workflow = [r["repo"] for r in org_repos if not spec_flags.get(r["repo"], False)]
    return {"missing": missing, "gone": gone, "not_workflow": not_workflow}


def add_stubs(registry_path, missing):
    path = Path(registry_path)
    original_text = path.read_text()
    text = original_text

    text = re.sub(r"^workflows:\s*\[\]\s*$", "workflows:", text, flags=re.MULTILINE)

    if not text.endswith("\n"):
        text += "\n"
    for item in missing:
        name = item["repo"].split("/", 1)[1]
        text += f"  - id: {name}\n    repo: {item['repo']}\n"

    try:
        data = yaml.safe_load(text)
        workflows = data.get("workflows", [])
        if not isinstance(workflows, list) or len(workflows) != len(missing) + len(yaml.safe_load(original_text).get("workflows", [])):
            path.write_text(original_text)
            raise RegistryError(f"could not append stubs to {path}")
    except (yaml.YAMLError, KeyError, TypeError):
        path.write_text(original_text)
        raise RegistryError(f"could not append stubs to {path}")

    path.write_text(text)
    return len(missing)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Find workflow repos in the org that are not in the registry.")
    parser.add_argument("--registry", default=str(HERE / "registry.yaml"))
    parser.add_argument("--org", default="wildlife-dynamics")
    parser.add_argument("--add", action="store_true", help="append missing repos to the registry as stubs")
    parser.add_argument("--json", action="store_true", help="print the missing list as JSON (for collect.py --unregistered)")
    args = parser.parse_args(argv)

    try:
        entries = load_registry(args.registry)
    except RegistryError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    client = GitHubClient()
    try:
        org_repos = list_org_repos(client, args.org)
    except GitHubError as e:
        print(f"warning: could not list org repos: {e}", file=sys.stderr)
        if args.json:
            print("[]")
        return 0
    spec_flags = {}
    for r in org_repos:
        try:
            spec_flags[r["repo"]] = has_spec(client, r["repo"])
        except GitHubError as e:
            print(f"warning: could not read {r['repo']}: {e}", file=sys.stderr)
            spec_flags[r["repo"]] = False
    result = diff(entries, org_repos, spec_flags)

    if args.json:
        print(json.dumps(result["missing"]))
    else:
        print(f"Workflow repos not in registry ({len(result['missing'])}):")
        for item in result["missing"]:
            print(f"  {item['repo']} ({item['visibility']})")
        print(f"Registry entries whose repo is gone or archived ({len(result['gone'])}):")
        for wid in result["gone"]:
            print(f"  {wid}")
        print(f"Org repos without spec.yaml ({len(result['not_workflow'])}):")
        for repo in result["not_workflow"]:
            print(f"  {repo}")
    if args.add and result["missing"]:
        n = add_stubs(args.registry, result["missing"])
        print(f"appended {n} stub(s) to {args.registry}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
