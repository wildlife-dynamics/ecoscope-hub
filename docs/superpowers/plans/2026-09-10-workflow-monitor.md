# Ecoscope Workflow Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A GitHub Pages site, rebuilt on a schedule from ecoscope-hub, listing every registered ecoscope workflow with its epic's Project status/priority, availability on Desktop and Web, outputs and indicators, CI state, and open work.

**Architecture:** A Python collector (`monitor/collect.py`) reads `monitor/registry.yaml`, queries GitHub REST + GraphQL and the public Desktop catalog, and writes one `data.json`. A discovery script (`monitor/discover.py`) lists org repos with a root `spec.yaml` and diffs them against the registry. A single dependency-free `monitor/index.html` renders the JSON. A GitHub Actions workflow runs tests → discover → collect → deploy-pages.

**Tech Stack:** Python ≥3.11, `requests`, `pyyaml`, `pytest`; a self-contained pixi manifest in `monitor/` (the root `pyproject.toml` is the legacy `wt` package env and is not touched). Vanilla HTML/CSS/JS. GitHub Actions `actions/upload-pages-artifact` + `actions/deploy-pages`.

**Spec:** `docs/superpowers/specs/2026-09-10-workflow-monitor-design.md`

## Global Constraints

- Registry holds only `id`, `repo`, `epic`. Nothing else is hand-managed in the hub.
- Epic issue types accepted: `Workflow` and `Epic`. Any other type → error recorded, fields still used.
- Status / priority / size come from the **Wildlife Dynamics** project (number `9`) item first, else the first project item that has those fields. Values copied verbatim, never validated.
- A **private** repo is never shown as available on Desktop or Web.
- Desktop catalog URL: `https://storage.googleapis.com/ecoscope-io-storage-public/ecoscope-desktop/hardcoded-template-catalog/workflow_templates.json`
- `VERSION.yaml` shape is `{MAJ: 1, MIN: 0, PATCH: 1}` → render as `1.0.1`.
- Deliverable types: `dashboard | report | file`. Component types: `map | plot | table | text | figure`.
- A per-repo failure lands in that record's `errors` list; the build fails only on an invalid registry or an uncaught exception.
- Tests are flat pytest functions (no classes). No new comments/docstrings on unchanged code.
- Page title: `Ecoscope Workflow Monitor`. No external scripts/styles. Works at 400px width.
- All git commits end with the attribution trailer given in the session (`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` + `Claude-Session:` line).

## File structure

```
monitor/
  pixi.toml            # python, requests, pyyaml, pytest; tasks: test, collect, discover
  pytest.ini           # pythonpath = .
  registry.yaml        # seeded with the 14 Workflow-typed epics found in the org
  indicators.yaml      # canonical indicator vocabulary
  gh.py                # GitHubClient: REST get/paginate/get_text, GraphQL, rate-limit retry
  metadata.py          # pure functions: registry validation, indicator + outputs normalisation, version parsing
  epic.py              # GraphQL query + parse_epic + fetch_epic
  collect.py           # repo facts, availability, CI, issues, record assembly, CLI
  discover.py          # org repo listing, spec.yaml detection, registry diff, --add/--json
  index.html           # the page
  sample-data.json     # fixture for opening index.html locally
  README.md            # how to run locally, how to add a workflow, the PAT
  tests/
    conftest.py        # FakeResponse, FakeSession, client fixture
    test_gh.py
    test_metadata.py
    test_epic.py
    test_collect.py
    test_discover.py
    test_live.py       # skipped without MONITOR_PAT/GITHUB_TOKEN
.github/workflows/monitor.yml
```

Every command below is run from the repo root (the worktree root). `PIXI="pixi run --manifest-path monitor/pixi.toml"`.

---

### Task 1: Environment, registry, and registry validation

**Files:**
- Create: `monitor/pixi.toml`, `monitor/pytest.ini`, `monitor/registry.yaml`, `monitor/metadata.py`, `monitor/tests/test_metadata.py`, `monitor/tests/__init__.py` (empty)

**Interfaces:**
- Produces: `metadata.load_registry(path: str | Path) -> list[dict]` raising `metadata.RegistryError` on invalid input; each dict has keys `id`, `repo` (str | None), `epic` (str | None).

- [ ] **Step 1: Create the pixi manifest and pytest config**

`monitor/pixi.toml`:
```toml
[workspace]
name = "ecoscope-workflow-monitor"
channels = ["conda-forge"]
platforms = ["osx-arm64", "linux-64"]

[dependencies]
python = ">=3.11"
requests = ">=2.31"
pyyaml = ">=6.0"
pytest = ">=8"

[tasks]
test = "pytest -q"
collect = "python collect.py"
discover = "python discover.py"
```

`monitor/pytest.ini`:
```ini
[pytest]
pythonpath = .
testpaths = tests
```

Run: `pixi install --manifest-path monitor/pixi.toml`
Expected: solves and writes `monitor/pixi.lock`. Commit the lock.

- [ ] **Step 2: Seed the registry**

`monitor/registry.yaml`:
```yaml
# One entry per ecoscope workflow. Status, priority, and projects are managed on the epic
# issue in GitHub Projects (https://github.com/orgs/wildlife-dynamics/projects/9), not here.
workflows:
  - id: wt-ndvi
    repo: wildlife-dynamics/ndvi
    epic: https://github.com/wildlife-dynamics/ndvi/issues/22
  - id: wt-download-events
    repo: wildlife-dynamics/wt-download-events
    epic: https://github.com/wildlife-dynamics/wt-download-events/issues/33
  - id: wt-download-patrols
    repo: wildlife-dynamics/wt-download-patrols
    epic: https://github.com/wildlife-dynamics/wt-download-patrols/issues/18
  - id: wt-download-subject-tracks
    repo: wildlife-dynamics/wt-download-subject-tracks
    epic: https://github.com/wildlife-dynamics/wt-download-subject-tracks/issues/21
  - id: wt-hydrological-monitoring
    repo: wildlife-dynamics/wt-hydrological-monitoring
  - id: patrol-effort-table
    repo: wildlife-dynamics/patrol-effort-table
    epic: https://github.com/wildlife-dynamics/patrol-effort-table/issues/1
  - id: mt-patrols
    repo: wildlife-dynamics/mt-patrols
    epic: https://github.com/wildlife-dynamics/mt-patrols/issues/4
  - id: patrol-encounter-rate-map
    repo: wildlife-dynamics/patrol-encounter-rate-map
    epic: https://github.com/wildlife-dynamics/patrol-encounter-rate-map/issues/3
  - id: namibia
    repo: wildlife-dynamics/namibia
    epic: https://github.com/wildlife-dynamics/namibia/issues/164
  - id: curacao-turtle-monitoring
    repo: wildlife-dynamics/curacao-turtle_monitoring
    epic: https://github.com/wildlife-dynamics/curacao-turtle_monitoring/issues/1
  - id: apn-exotic-animal-control
    repo: wildlife-dynamics/APN
    epic: https://github.com/wildlife-dynamics/APN/issues/180
  - id: apn-weapon-use-report
    repo: wildlife-dynamics/APN
    epic: https://github.com/wildlife-dynamics/APN/issues/164
  - id: dr-whale-sightings
    repo: wildlife-dynamics/Dominican.Republic-Whale_Sighting
    epic: https://github.com/wildlife-dynamics/Dominican.Republic-Whale_Sighting/issues/1
  - id: latam-patrol-summary
    repo: wildlife-dynamics/latam-patrol_summary
    epic: https://github.com/wildlife-dynamics/latam-patrol_summary/issues/2
  - id: eden-community-engagement
    repo: wildlife-dynamics/eden
    epic: https://github.com/wildlife-dynamics/eden/issues/1
```

- [ ] **Step 3: Write the failing registry tests**

`monitor/tests/test_metadata.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pixi run --manifest-path monitor/pixi.toml pytest tests/test_metadata.py -q`
Expected: ImportError / `No module named 'metadata'`.

- [ ] **Step 5: Implement `load_registry`**

`monitor/metadata.py`:
```python
import re
from pathlib import Path

import yaml

EPIC_URL_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/issues/(\d+)/?$")


class RegistryError(Exception):
    pass


def parse_epic_url(url):
    m = EPIC_URL_RE.match(url or "")
    if not m:
        raise RegistryError(f"epic is not a GitHub issue URL: {url!r}")
    return m.group(1), m.group(2), int(m.group(3))


def load_registry(path):
    data = yaml.safe_load(Path(path).read_text()) or {}
    raw = data.get("workflows")
    if not isinstance(raw, list):
        raise RegistryError("registry must have a top-level 'workflows' list")
    entries, seen = [], set()
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or not item.get("id"):
            raise RegistryError(f"entry {i} is missing an id")
        wid = str(item["id"])
        if wid in seen:
            raise RegistryError(f"duplicate id: {wid}")
        seen.add(wid)
        repo = item.get("repo") or None
        epic = item.get("epic") or None
        if not repo and not epic:
            raise RegistryError(f"{wid}: needs repo or epic")
        if epic:
            parse_epic_url(epic)
        entries.append({"id": wid, "repo": repo, "epic": epic})
    return entries
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pixi run --manifest-path monitor/pixi.toml pytest tests/test_metadata.py -q`
Expected: 5 passed.

- [ ] **Step 7: Check the seeded registry loads**

Run: `pixi run --manifest-path monitor/pixi.toml python -c "from metadata import load_registry; print(len(load_registry('registry.yaml')))"`
Expected: `15`.

- [ ] **Step 8: Commit**

```bash
git add monitor/pixi.toml monitor/pixi.lock monitor/pytest.ini monitor/registry.yaml monitor/metadata.py monitor/tests/__init__.py monitor/tests/test_metadata.py
git commit -m "monitor: pixi env, seeded registry, registry validation"
```

---

### Task 2: GitHub client with fake transport

**Files:**
- Create: `monitor/gh.py`, `monitor/tests/conftest.py`, `monitor/tests/test_gh.py`

**Interfaces:**
- Produces:
  - `gh.GitHubClient(token: str | None = None, session=None)`; token defaults to `MONITOR_PAT` then `GITHUB_TOKEN` env vars.
  - `client.get(path, params=None) -> Any` (JSON), raises `gh.NotFound` on 404, `gh.GitHubError` on other ≥400.
  - `client.paginate(path, params=None) -> list` following `Link: rel=next`.
  - `client.get_text(repo, path, ref) -> str` raw file contents, raises `NotFound`.
  - `client.graphql(query, variables) -> dict` returns the `data` object; raises `GitHubError` if the body has `errors`.
  - `client.session` exposed so callers can fetch non-GitHub URLs (the catalog) through the same session.
- Test helpers in conftest: `FakeResponse(status=200, body=None, text=None, headers=None, links=None)`, `FakeSession()` with `.add(method, url, response_or_callable)` and `.calls` list; fixture `session` and fixture `client`.

- [ ] **Step 1: Write the fakes**

`monitor/tests/conftest.py`:
```python
import json

import pytest

from gh import GitHubClient


class FakeResponse:
    def __init__(self, status=200, body=None, text=None, headers=None, links=None):
        self.status_code = status
        self._body = body
        self.text = text if text is not None else json.dumps(body)
        self.headers = headers or {}
        self.links = links or {}

    def json(self):
        return self._body


class FakeSession:
    def __init__(self):
        self.routes = {}
        self.calls = []

    def add(self, method, url, response):
        self.routes.setdefault((method, url), []).append(response)

    def request(self, method, url, headers=None, timeout=None, params=None, json=None):
        self.calls.append({"method": method, "url": url, "params": params, "json": json, "headers": headers})
        queue = self.routes.get((method, url))
        if not queue:
            return FakeResponse(404, {"message": "Not Found"})
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        return item(params, json) if callable(item) else item


@pytest.fixture
def session():
    return FakeSession()


@pytest.fixture
def client(session):
    return GitHubClient(token="t", session=session)
```

- [ ] **Step 2: Write the failing client tests**

`monitor/tests/test_gh.py`:
```python
import pytest

from conftest import FakeResponse
from gh import API, GitHubError, NotFound


def test_get_returns_json_and_sends_bearer(client, session):
    session.add("GET", f"{API}/repos/o/r", FakeResponse(200, {"name": "r"}))
    assert client.get("/repos/o/r") == {"name": "r"}
    assert session.calls[0]["headers"]["Authorization"] == "Bearer t"


def test_get_raises_not_found(client, session):
    with pytest.raises(NotFound):
        client.get("/repos/o/missing")


def test_get_raises_on_server_error(client, session):
    session.add("GET", f"{API}/repos/o/r", FakeResponse(500, {"message": "boom"}))
    with pytest.raises(GitHubError, match="500"):
        client.get("/repos/o/r")


def test_paginate_follows_next_link(client, session):
    session.add("GET", f"{API}/repos/o/r/issues", FakeResponse(200, [1, 2], links={"next": {"url": "https://x/page2"}}))
    session.add("GET", "https://x/page2", FakeResponse(200, [3]))
    assert client.paginate("/repos/o/r/issues", {"state": "open"}) == [1, 2, 3]
    assert session.calls[0]["params"] == {"state": "open", "per_page": 100}
    assert session.calls[1]["params"] is None


def test_get_text_uses_raw_accept(client, session):
    session.add("GET", f"{API}/repos/o/r/contents/spec.yaml", FakeResponse(200, text="id: x\n"))
    assert client.get_text("o/r", "spec.yaml", "main") == "id: x\n"
    call = session.calls[0]
    assert call["headers"]["Accept"] == "application/vnd.github.raw+json"
    assert call["params"] == {"ref": "main"}


def test_graphql_returns_data_and_raises_on_errors(client, session):
    session.add("POST", f"{API}/graphql", FakeResponse(200, {"data": {"ok": 1}}))
    assert client.graphql("q", {"a": 1}) == {"ok": 1}
    assert session.calls[0]["json"] == {"query": "q", "variables": {"a": 1}}
    assert session.calls[0]["headers"]["GraphQL-Features"] == "issue_types"
    session.add("POST", f"{API}/graphql", FakeResponse(200, {"errors": [{"message": "bad"}]}))
    with pytest.raises(GitHubError, match="bad"):
        client.graphql("q", {})


def test_retries_once_after_rate_limit(client, session, monkeypatch):
    monkeypatch.setattr("gh.time.sleep", lambda s: None)
    session.add("GET", f"{API}/x", FakeResponse(403, {"message": "rate"}, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "0"}))
    session.add("GET", f"{API}/x", FakeResponse(200, {"ok": True}))
    assert client.get("/x") == {"ok": True}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pixi run --manifest-path monitor/pixi.toml pytest tests/test_gh.py -q`
Expected: `No module named 'gh'`.

- [ ] **Step 4: Implement the client**

`monitor/gh.py`:
```python
import os
import time

import requests

API = "https://api.github.com"


class GitHubError(Exception):
    pass


class NotFound(GitHubError):
    pass


class GitHubClient:
    def __init__(self, token=None, session=None):
        self.token = token or os.environ.get("MONITOR_PAT") or os.environ.get("GITHUB_TOKEN")
        self.session = session or requests.Session()

    def _headers(self, extra=None):
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if extra:
            headers.update(extra)
        return headers

    def _request(self, method, url, headers=None, **kwargs):
        response = None
        for _ in range(3):
            response = self.session.request(method, url, headers=self._headers(headers), timeout=30, **kwargs)
            limited = response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0"
            if not limited:
                return response
            reset = int(response.headers.get("X-RateLimit-Reset", "0"))
            time.sleep(max(1, min(reset - time.time(), 120)))
        return response

    def _check(self, response, what):
        if response.status_code == 404:
            raise NotFound(what)
        if response.status_code >= 400:
            raise GitHubError(f"{response.status_code} {what}: {response.text[:200]}")

    def get(self, path, params=None):
        response = self._request("GET", API + path, params=params)
        self._check(response, path)
        return response.json()

    def paginate(self, path, params=None):
        params = dict(params or {}, per_page=100)
        url, items = API + path, []
        while url:
            response = self._request("GET", url, params=params)
            self._check(response, path)
            items.extend(response.json())
            url = response.links.get("next", {}).get("url")
            params = None
        return items

    def get_text(self, repo, path, ref):
        response = self._request(
            "GET",
            f"{API}/repos/{repo}/contents/{path}",
            headers={"Accept": "application/vnd.github.raw+json"},
            params={"ref": ref},
        )
        self._check(response, f"{repo}:{path}@{ref}")
        return response.text

    def graphql(self, query, variables):
        response = self._request(
            "POST", API + "/graphql", headers={"GraphQL-Features": "issue_types"}, json={"query": query, "variables": variables}
        )
        self._check(response, "graphql")
        body = response.json()
        if body.get("errors"):
            raise GitHubError("; ".join(e.get("message", "?") for e in body["errors"]))
        return body["data"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pixi run --manifest-path monitor/pixi.toml pytest tests/test_gh.py -q`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add monitor/gh.py monitor/tests/conftest.py monitor/tests/test_gh.py
git commit -m "monitor: GitHub client with pagination, raw contents, GraphQL, rate-limit retry"
```

---

### Task 3: Indicator vocabulary, outputs normalisation, version parsing

**Files:**
- Create: `monitor/indicators.yaml`
- Modify: `monitor/metadata.py` (append)
- Modify: `monitor/tests/test_metadata.py` (append)

**Interfaces:**
- Produces:
  - `metadata.load_indicators(path) -> dict[str, str]` mapping lower-cased alias/label/id → canonical id.
  - `metadata.normalize_indicators(raw: list, vocab: dict) -> tuple[list[str], list[str]]` → `(canonical_ids, unknown_verbatim)`; accepts strings or `{name: ...}` dicts; de-duplicated, order preserved.
  - `metadata.normalize_outputs(meta: dict | None, fallback_name: str, vocab: dict) -> tuple[list[dict], list[str], list[str]]` → `(outputs, all_indicators, all_unknown)`. Each output: `{name, type, description, components: [{name, type, description, indicators}]}`.
  - `metadata.parse_version(text: str) -> str | None` → `"1.0.1"` from `{MAJ: 1, MIN: 0, PATCH: 1}`.
  - Constants `metadata.DELIVERABLE_TYPES`, `metadata.COMPONENT_TYPES`.

- [ ] **Step 1: Write the vocabulary file**

`monitor/indicators.yaml`:
```yaml
# Canonical indicator ids. The collector maps every indicator named in a workflow's spec
# metadata to one of these via label or alias (case-insensitive). Unknown names are kept
# verbatim and flagged on the monitor.
indicators:
  ndvi:
    label: NDVI
    description: Normalized Difference Vegetation Index from satellite imagery
    aliases: [vegetation index, vegetation health]
  patrol-distance:
    label: Patrol distance
    description: Distance covered by patrols over the period
    aliases: [distance patrolled, patrol km]
  patrol-effort:
    label: Patrol effort
    description: Patrol time, count, or coverage as an effort measure
    aliases: [patrol time, patrol hours, patrol count]
  encounter-rate:
    label: Encounter rate
    description: Events observed per unit of patrol effort
    aliases: [encounter rates]
  trajectory:
    label: Trajectory
    description: Subject or vehicle movement tracks
    aliases: [tracks, movement, subject tracks]
  event-count:
    label: Event count
    description: Number of events by type, time, or area
    aliases: [events, event counts, event summary]
  water-level:
    label: Water level
    description: Hydrological water level or flow measurements
    aliases: [river level, flow, hydrology]
```

- [ ] **Step 2: Write the failing tests**

Append to `monitor/tests/test_metadata.py`:
```python
from metadata import load_indicators, normalize_indicators, normalize_outputs, parse_version


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


def test_normalize_outputs_nested_shape(vocab):
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
            }
        ]
    }
    outputs, indicators, unknown = normalize_outputs(meta, "X", vocab)
    assert outputs == [
        {
            "name": "NDVI Dashboard",
            "type": "dashboard",
            "description": "d",
            "components": [
                {"name": "NDVI Map", "type": "map", "description": "m", "indicators": ["ndvi"]},
                {"name": "Trend", "type": "plot", "description": "", "indicators": ["ndvi"]},
            ],
        }
    ]
    assert indicators == ["ndvi"]
    assert unknown == []


def test_normalize_outputs_flat_shape_becomes_implicit_dashboard(vocab):
    meta = {
        "outputs": [
            {"name": "NDVI Dashboard", "type": "dashboard", "indicators": [{"name": "NDVI"}]},
            {"name": "NDVI Map", "type": "map", "description": "m", "indicators": [{"name": "NDVI"}]},
            {"name": "NDVI Data", "type": "file", "indicators": [{"name": "NDVI"}]},
        ]
    }
    outputs, indicators, unknown = normalize_outputs(meta, "NDVI Workflow", vocab)
    assert [o["type"] for o in outputs] == ["dashboard", "file"]
    dashboard = outputs[0]
    assert dashboard["name"] == "NDVI Dashboard"
    assert dashboard["components"] == [{"name": "NDVI Map", "type": "map", "description": "m", "indicators": ["ndvi"]}]
    assert outputs[1]["components"] == []
    assert indicators == ["ndvi"]


def test_normalize_outputs_flat_without_dashboard_entry_names_it_after_workflow(vocab):
    meta = {"outputs": [{"name": "Map", "type": "map", "indicators": ["ndvi"]}]}
    outputs, _, _ = normalize_outputs(meta, "NDVI Workflow", vocab)
    assert outputs[0]["name"] == "NDVI Workflow Dashboard"
    assert outputs[0]["type"] == "dashboard"


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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pixi run --manifest-path monitor/pixi.toml pytest tests/test_metadata.py -q`
Expected: ImportError on `load_indicators`.

- [ ] **Step 4: Implement**

Append to `monitor/metadata.py`:
```python
DELIVERABLE_TYPES = {"dashboard", "report", "file"}
COMPONENT_TYPES = {"map", "plot", "table", "text", "figure"}


def load_indicators(path):
    data = yaml.safe_load(Path(path).read_text()) or {}
    vocab = {}
    for canonical, spec in (data.get("indicators") or {}).items():
        spec = spec or {}
        names = [canonical, spec.get("label") or canonical, *(spec.get("aliases") or [])]
        for name in names:
            vocab[str(name).strip().lower()] = canonical
    return vocab


def _indicator_name(item):
    if isinstance(item, dict):
        return str(item.get("name") or "").strip()
    return str(item or "").strip()


def normalize_indicators(raw, vocab):
    canonical, unknown = [], []
    for item in raw or []:
        name = _indicator_name(item)
        if not name:
            continue
        key = name.lower()
        if key in vocab:
            if vocab[key] not in canonical:
                canonical.append(vocab[key])
        elif name not in unknown:
            unknown.append(name)
    return canonical, unknown


def _component(entry, vocab):
    indicators, unknown = normalize_indicators(entry.get("indicators"), vocab)
    return (
        {
            "name": str(entry.get("name") or ""),
            "type": str(entry.get("type") or ""),
            "description": str(entry.get("description") or ""),
            "indicators": indicators,
        },
        unknown,
    )


def normalize_outputs(meta, fallback_name, vocab):
    raw = (meta or {}).get("outputs") or []
    outputs, all_indicators, all_unknown = [], [], []
    implicit = None

    def note(indicators, unknown):
        for i in indicators:
            if i not in all_indicators:
                all_indicators.append(i)
        for u in unknown:
            if u not in all_unknown:
                all_unknown.append(u)

    for entry in raw:
        if not isinstance(entry, dict):
            continue
        etype = str(entry.get("type") or "")
        if etype in COMPONENT_TYPES:
            component, unknown = _component(entry, vocab)
            note(component["indicators"], unknown)
            if implicit is None:
                implicit = {"name": f"{fallback_name} Dashboard", "type": "dashboard", "description": "", "components": []}
                outputs.append(implicit)
            implicit["components"].append(component)
            continue
        components = []
        for c in entry.get("components") or []:
            if isinstance(c, dict):
                component, unknown = _component(c, vocab)
                note(component["indicators"], unknown)
                components.append(component)
        top_indicators, unknown = normalize_indicators(entry.get("indicators"), vocab)
        note(top_indicators, unknown)
        output = {
            "name": str(entry.get("name") or ""),
            "type": etype,
            "description": str(entry.get("description") or ""),
            "components": components,
        }
        if etype == "dashboard" and implicit is None:
            implicit = output
        outputs.append(output)
    return outputs, all_indicators, all_unknown


def parse_version(text):
    try:
        data = yaml.safe_load(text or "")
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    try:
        return f"{int(data['MAJ'])}.{int(data['MIN'])}.{int(data['PATCH'])}"
    except (KeyError, TypeError, ValueError):
        return None
```

Note on the flat shape: a top-level `dashboard` entry that appears *before* the flat `map`/`plot` entries becomes the implicit container (so wt-ndvi's "NDVI Dashboard" keeps its name); if none exists, one is synthesised as `<fallback_name> Dashboard`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pixi run --manifest-path monitor/pixi.toml pytest tests/test_metadata.py -q`
Expected: 13 passed.

- [ ] **Step 6: Commit**

```bash
git add monitor/indicators.yaml monitor/metadata.py monitor/tests/test_metadata.py
git commit -m "monitor: indicator vocabulary, outputs normalisation, VERSION.yaml parsing"
```

---

### Task 4: Epic fetch and parse

**Files:**
- Create: `monitor/epic.py`, `monitor/tests/test_epic.py`

**Interfaces:**
- Consumes: `gh.GitHubClient.graphql`, `metadata.parse_epic_url`.
- Produces:
  - `epic.WD_PROJECT_NUMBER = 9`, `epic.EPIC_TYPES = {"Workflow", "Epic"}`.
  - `epic.fetch_epic(client, url) -> tuple[dict, list[str]]` → `(epic_record, errors)`. Raises `gh.GitHubError`/`gh.NotFound` if the issue cannot be read at all.
  - `epic_record` keys: `url, title, state, type, status, priority, size, projects: [{number,title,url}], sub_issues: [{number, repo, title, state, type, url}], sub_issues_total, sub_issues_completed`.

- [ ] **Step 1: Write the failing tests**

`monitor/tests/test_epic.py`:
```python
import pytest

from conftest import FakeResponse
from epic import fetch_epic
from gh import API, GitHubError


def issue_payload(sub_nodes, has_next=False, project_items=None, issue_type="Workflow"):
    return {
        "data": {
            "repository": {
                "issue": {
                    "title": "NDVI",
                    "state": "OPEN",
                    "url": "https://github.com/o/r/issues/1",
                    "issueType": {"name": issue_type} if issue_type else None,
                    "subIssuesSummary": {"total": 3, "completed": 1},
                    "projectItems": {"nodes": project_items or []},
                    "subIssues": {
                        "pageInfo": {"hasNextPage": has_next, "endCursor": "c1" if has_next else None},
                        "nodes": sub_nodes,
                    },
                }
            }
        }
    }


def project_item(number, title, **fields):
    nodes = [{"name": v, "field": {"name": k}} for k, v in fields.items()]
    nodes.append({})
    return {"project": {"number": number, "title": title, "url": f"https://github.com/orgs/o/projects/{number}"}, "fieldValues": {"nodes": nodes}}


def sub(number, state="OPEN", itype="Bug", repo="o/other"):
    return {"number": number, "title": f"s{number}", "state": state, "url": f"https://github.com/{repo}/issues/{number}", "issueType": {"name": itype}, "repository": {"nameWithOwner": repo}}


def test_fetch_epic_reads_fields_from_wd_project_first(client, session):
    items = [project_item(41, "Eden", Status="Done", Priority="P3"), project_item(9, "Wildlife Dynamics", Status="In progress", Priority="P1", Size="M")]
    session.add("POST", f"{API}/graphql", FakeResponse(200, issue_payload([sub(741)], project_items=items)))
    record, errors = fetch_epic(client, "https://github.com/o/r/issues/1")
    assert errors == []
    assert record["status"] == "In progress"
    assert record["priority"] == "P1"
    assert record["size"] == "M"
    assert [p["title"] for p in record["projects"]] == ["Eden", "Wildlife Dynamics"]
    assert record["type"] == "Workflow"
    assert record["sub_issues"] == [{"number": 741, "repo": "o/other", "title": "s741", "state": "OPEN", "type": "Bug", "url": "https://github.com/o/other/issues/741"}]
    assert record["sub_issues_total"] == 3
    assert record["sub_issues_completed"] == 1
    assert session.calls[0]["json"]["variables"] == {"owner": "o", "name": "r", "number": 1, "after": None}


def test_fetch_epic_falls_back_to_first_project_with_fields(client, session):
    items = [project_item(41, "Eden"), project_item(40, "KBoPT", Status="Ready", Priority="P2")]
    session.add("POST", f"{API}/graphql", FakeResponse(200, issue_payload([], project_items=items)))
    record, _ = fetch_epic(client, "https://github.com/o/r/issues/1")
    assert record["status"] == "Ready"
    assert record["priority"] == "P2"
    assert record["size"] is None


def test_fetch_epic_paginates_sub_issues(client, session):
    session.add("POST", f"{API}/graphql", FakeResponse(200, issue_payload([sub(1)], has_next=True)))
    session.add("POST", f"{API}/graphql", FakeResponse(200, issue_payload([sub(2)])))
    record, _ = fetch_epic(client, "https://github.com/o/r/issues/1")
    assert [s["number"] for s in record["sub_issues"]] == [1, 2]
    assert session.calls[1]["json"]["variables"]["after"] == "c1"


def test_fetch_epic_flags_unexpected_type(client, session):
    session.add("POST", f"{API}/graphql", FakeResponse(200, issue_payload([], issue_type="Bug")))
    record, errors = fetch_epic(client, "https://github.com/o/r/issues/1")
    assert record["type"] == "Bug"
    assert errors == ["epic issue type is 'Bug', expected Workflow or Epic"]


def test_fetch_epic_missing_type_is_flagged(client, session):
    session.add("POST", f"{API}/graphql", FakeResponse(200, issue_payload([], issue_type=None)))
    record, errors = fetch_epic(client, "https://github.com/o/r/issues/1")
    assert record["type"] is None
    assert errors == ["epic issue type is None, expected Workflow or Epic"]


def test_fetch_epic_raises_when_issue_missing(client, session):
    session.add("POST", f"{API}/graphql", FakeResponse(200, {"data": {"repository": {"issue": None}}}))
    with pytest.raises(GitHubError, match="not found"):
        fetch_epic(client, "https://github.com/o/r/issues/1")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run --manifest-path monitor/pixi.toml pytest tests/test_epic.py -q`
Expected: `No module named 'epic'`.

- [ ] **Step 3: Implement**

`monitor/epic.py`:
```python
from gh import GitHubError
from metadata import parse_epic_url

WD_PROJECT_NUMBER = 9
EPIC_TYPES = {"Workflow", "Epic"}
FIELD_KEYS = {"Status": "status", "Priority": "priority", "Size": "size"}

QUERY = """
query($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    issue(number: $number) {
      title state url
      issueType { name }
      subIssuesSummary { total completed }
      projectItems(first: 20) {
        nodes {
          project { number title url }
          fieldValues(first: 30) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field { ... on ProjectV2SingleSelectField { name } }
              }
            }
          }
        }
      }
      subIssues(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          number title state url
          issueType { name }
          repository { nameWithOwner }
        }
      }
    }
  }
}
"""


def _project_fields(item):
    fields = {}
    for node in item.get("fieldValues", {}).get("nodes", []):
        field_name = (node.get("field") or {}).get("name")
        if field_name in FIELD_KEYS and node.get("name") is not None:
            fields[FIELD_KEYS[field_name]] = node["name"]
    return fields


def _pick_fields(items):
    by_number = {item["project"]["number"]: _project_fields(item) for item in items if item.get("project")}
    if by_number.get(WD_PROJECT_NUMBER):
        return by_number[WD_PROJECT_NUMBER]
    for fields in by_number.values():
        if fields:
            return fields
    return {}


def _sub_issue(node):
    return {
        "number": node["number"],
        "repo": (node.get("repository") or {}).get("nameWithOwner"),
        "title": node.get("title"),
        "state": node.get("state"),
        "type": (node.get("issueType") or {}).get("name"),
        "url": node.get("url"),
    }


def fetch_epic(client, url):
    owner, name, number = parse_epic_url(url)
    after, issue, sub_issues = None, None, []
    while True:
        data = client.graphql(QUERY, {"owner": owner, "name": name, "number": number, "after": after})
        page = (data.get("repository") or {}).get("issue")
        if page is None:
            raise GitHubError(f"epic not found: {url}")
        issue = issue or page
        sub_issues.extend(_sub_issue(n) for n in page["subIssues"]["nodes"])
        info = page["subIssues"]["pageInfo"]
        if not info.get("hasNextPage"):
            break
        after = info["endCursor"]

    items = issue.get("projectItems", {}).get("nodes", [])
    fields = _pick_fields(items)
    issue_type = (issue.get("issueType") or {}).get("name")
    errors = []
    if issue_type not in EPIC_TYPES:
        errors.append(f"epic issue type is {issue_type!r}, expected Workflow or Epic")
    summary = issue.get("subIssuesSummary") or {}
    record = {
        "url": issue.get("url") or url,
        "title": issue.get("title"),
        "state": issue.get("state"),
        "type": issue_type,
        "status": fields.get("status"),
        "priority": fields.get("priority"),
        "size": fields.get("size"),
        "projects": [item["project"] for item in items if item.get("project")],
        "sub_issues": sub_issues,
        "sub_issues_total": summary.get("total", len(sub_issues)),
        "sub_issues_completed": summary.get("completed", 0),
    }
    return record, errors
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pixi run --manifest-path monitor/pixi.toml pytest tests/test_epic.py -q`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add monitor/epic.py monitor/tests/test_epic.py
git commit -m "monitor: fetch epic status, priority, projects, and sub-issues via GraphQL"
```

---

### Task 5: Repo facts, availability, CI, issues, and record assembly

**Files:**
- Create: `monitor/collect.py`, `monitor/tests/test_collect.py`

**Interfaces:**
- Consumes: `gh.GitHubClient`, `epic.fetch_epic`, `metadata.load_registry / load_indicators / normalize_outputs / parse_version`.
- Produces:
  - `collect.CATALOG_URL` (constant from Global Constraints).
  - `collect.fetch_catalog(session) -> dict[str, str]` mapping `owner/repo` (lower-cased) → `version_file_path`.
  - `collect.find_version_path(client, repo, ref) -> str | None` (first `*-workflow/VERSION.yaml` in the tree).
  - `collect.collect_workflow(entry, client, catalog, vocab) -> dict` (one record; never raises for per-repo problems).
  - `collect.build(entries, client, catalog, vocab, unregistered) -> dict` (the snapshot).
  - `collect.main(argv) -> int` with `--registry`, `--indicators`, `--out`, `--only`, `--unregistered`.

- [ ] **Step 1: Write the failing tests**

`monitor/tests/test_collect.py`:
```python
import json

from conftest import FakeResponse
from collect import CATALOG_URL, build, collect_workflow, fetch_catalog, find_version_path, main
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
    assert record["visibility"] == "public"
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


def test_collect_workflow_private_repo_has_no_availability(client, session):
    add_epic(session)
    add_repo(session, private=True)
    add_spec(session)
    session.add("GET", f"{API}/repos/o/r/branches/ecoscope-web", FakeResponse(200, {"name": "ecoscope-web"}))
    add_ci(session)
    add_issues(session)
    record = collect_workflow(full_entry(), client, {"o/r": "pkg-workflow/VERSION.yaml"}, VOCAB)
    assert record["visibility"] == "private"
    assert record["desktop_version"] is None
    assert record["web_version"] is None
    assert not any("VERSION" in c["url"] for c in session.calls)


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

    session2 = type(session)()
    client2 = type(client)(token="t", session=session2)
    add_epic(session2)
    add_repo(session2)
    add_ci(session2)
    add_issues(session2)
    record = collect_workflow(full_entry(), client2, {}, VOCAB)
    assert record["spec_missing"] is True and record["metadata_missing"] is True


def test_collect_workflow_repo_404_records_error_but_keeps_epic(client, session):
    add_epic(session)
    record = collect_workflow(full_entry(), client, {}, VOCAB)
    assert record["epic"]["status"] == "Ready"
    assert record["visibility"] is None
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


def test_build_isolates_failures_and_stamps_time(client, session):
    add_epic(session)
    add_repo(session)
    add_spec(session)
    add_ci(session)
    add_issues(session)
    entries = [full_entry(), {"id": "gone", "repo": "o/gone", "epic": None}]
    snapshot = build(entries, client, {}, VOCAB, [{"repo": "o/new", "visibility": "public"}])
    assert snapshot["generated_at"].endswith("Z")
    assert [w["id"] for w in snapshot["workflows"]] == ["r", "gone"]
    assert snapshot["workflows"][1]["errors"]
    assert snapshot["unregistered"] == [{"repo": "o/new", "visibility": "public"}]


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
    unregistered.write_text('[{"repo": "o/new", "visibility": "public"}]')
    out = tmp_path / "build" / "data.json"
    code = main(["--registry", str(registry), "--indicators", str(indicators), "--out", str(out), "--only", "r", "--unregistered", str(unregistered)])
    assert code == 0
    data = json.loads(out.read_text())
    assert [w["id"] for w in data["workflows"]] == ["r"]
    assert data["unregistered"][0]["repo"] == "o/new"


def test_main_fails_on_invalid_registry(tmp_path, capsys):
    registry = tmp_path / "registry.yaml"
    registry.write_text("workflows:\n  - id: a\n")
    code = main(["--registry", str(registry), "--indicators", str(registry), "--out", str(tmp_path / "d.json")])
    assert code == 2
    assert "repo or epic" in capsys.readouterr().err
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run --manifest-path monitor/pixi.toml pytest tests/test_collect.py -q`
Expected: `No module named 'collect'`.

- [ ] **Step 3: Implement**

`monitor/collect.py`:
```python
import argparse
import json
import sys
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


def _ci(client, repo, branch):
    try:
        runs = client.get(f"/repos/{repo}/actions/workflows/test.yml/runs", params={"branch": branch, "per_page": 1})
    except NotFound:
        return None, None
    latest = (runs.get("workflow_runs") or [None])[0]
    if not latest:
        return None, None
    return latest.get("conclusion"), latest.get("html_url")


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
        if "pull_request" not in i
    ]


def _empty_record(entry):
    return {
        "id": entry["id"],
        "repo": entry.get("repo"),
        "epic": None,
        "visibility": None,
        "archived": None,
        "name": entry["id"],
        "description": "",
        "maintainers": [],
        "outputs": [],
        "indicators": [],
        "unknown_indicators": [],
        "metadata_missing": True,
        "spec_missing": True,
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
        except GitHubError as e:
            errors.append(f"epic: {e}")

    repo = entry.get("repo")
    if not repo:
        return record

    try:
        info = client.get(f"/repos/{repo}")
    except NotFound:
        errors.append(f"repo not found: {repo}")
        return record
    except GitHubError as e:
        errors.append(f"repo: {e}")
        return record
    record["visibility"] = "private" if info.get("private") else "public"
    record["archived"] = bool(info.get("archived"))
    branch = info.get("default_branch") or "main"

    meta = None
    try:
        spec = yaml.safe_load(client.get_text(repo, "spec.yaml", branch)) or {}
        record["spec_missing"] = False
        meta = spec.get("metadata") if isinstance(spec, dict) else None
    except NotFound:
        pass
    except (GitHubError, yaml.YAMLError) as e:
        errors.append(f"spec.yaml: {e}")
    if isinstance(meta, dict):
        record["metadata_missing"] = False
        record["name"] = str(meta.get("name") or entry["id"])
        record["description"] = str(meta.get("description") or "")
        record["maintainers"] = [m for m in meta.get("maintainers") or [] if isinstance(m, dict)]
        record["outputs"], record["indicators"], record["unknown_indicators"] = normalize_outputs(meta, record["name"], vocab)

    if record["visibility"] == "public":
        version_path = catalog.get(repo.lower())
        try:
            if version_path:
                record["desktop_version"] = _read_version(client, repo, "main", version_path)
            if _branch_exists(client, repo, WEB_BRANCH):
                path = version_path or find_version_path(client, repo, WEB_BRANCH)
                if path:
                    record["web_version"] = _read_version(client, repo, WEB_BRANCH, path)
        except GitHubError as e:
            errors.append(f"version: {e}")

    try:
        record["ci_status"], record["ci_url"] = _ci(client, repo, branch)
    except GitHubError as e:
        errors.append(f"ci: {e}")

    try:
        record["issues"] = _issues(client, repo)
        record["open_issue_count"] = len(record["issues"])
    except GitHubError as e:
        errors.append(f"issues: {e}")

    return record


def build(entries, client, catalog, vocab, unregistered):
    workflows = []
    for entry in entries:
        try:
            workflows.append(collect_workflow(entry, client, catalog, vocab))
        except Exception as e:  # noqa: BLE001 - one bad repo must not blank the page
            record = _empty_record(entry)
            record["errors"].append(f"unexpected: {e!r}")
            workflows.append(record)
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
    except (RegistryError, OSError, yaml.YAMLError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.only:
        entries = [e for e in entries if e["id"] in set(args.only)]

    client = GitHubClient()
    try:
        catalog = fetch_catalog(client.session)
    except Exception as e:  # noqa: BLE001
        print(f"warning: catalog unavailable ({e}); desktop versions will be empty", file=sys.stderr)
        catalog = {}
    unregistered = json.loads(Path(args.unregistered).read_text()) if args.unregistered else []

    snapshot = build(entries, client, catalog, vocab, unregistered)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, indent=2, sort_keys=False) + "\n")
    errors = sum(len(w["errors"]) for w in snapshot["workflows"])
    print(f"wrote {out} ({len(snapshot['workflows'])} workflows, {errors} errors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pixi run --manifest-path monitor/pixi.toml pytest tests/test_collect.py -q`
Expected: 15 passed.

- [ ] **Step 5: Run the whole suite**

Run: `pixi run --manifest-path monitor/pixi.toml test`
Expected: all green (5 + 8 + 7 + 6 + 15 = 41 passed).

- [ ] **Step 6: Commit**

```bash
git add monitor/collect.py monitor/tests/test_collect.py
git commit -m "monitor: collector assembles per-workflow records and writes data.json"
```

---

### Task 6: Discovery script

**Files:**
- Create: `monitor/discover.py`, `monitor/tests/test_discover.py`

**Interfaces:**
- Consumes: `gh.GitHubClient`, `metadata.load_registry`.
- Produces:
  - `discover.list_org_repos(client, org) -> list[dict]` each `{repo, visibility, archived}`.
  - `discover.has_spec(client, repo) -> bool`.
  - `discover.diff(entries, org_repos, spec_flags: dict[str, bool]) -> dict` with keys `missing`, `gone`, `not_workflow` (lists of `{repo, visibility}` / registry ids).
  - `discover.add_stubs(registry_path, missing) -> int` appends `- id: <name>` / `repo:` stubs; returns count.
  - `discover.main(argv) -> int` with `--registry`, `--org` (default `wildlife-dynamics`), `--add`, `--json`.

- [ ] **Step 1: Write the failing tests**

`monitor/tests/test_discover.py`:
```python
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
    assert list_org_repos(client, "wd") == [{"repo": "wd/a", "visibility": "public", "archived": False}]
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pixi run --manifest-path monitor/pixi.toml pytest tests/test_discover.py -q`
Expected: `No module named 'discover'`.

- [ ] **Step 3: Implement**

`monitor/discover.py`:
```python
import argparse
import json
import sys
from pathlib import Path

from gh import GitHubClient, NotFound
from metadata import RegistryError, load_registry

HERE = Path(__file__).parent


def list_org_repos(client, org):
    repos = client.paginate(f"/orgs/{org}/repos", params={"type": "all"})
    return [
        {"repo": r["full_name"], "visibility": "private" if r.get("private") else "public", "archived": False}
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
    text = path.read_text()
    if not text.endswith("\n"):
        text += "\n"
    for item in missing:
        name = item["repo"].split("/", 1)[1]
        text += f"  - id: {name}\n    repo: {item['repo']}\n"
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
    org_repos = list_org_repos(client, args.org)
    spec_flags = {r["repo"]: has_spec(client, r["repo"]) for r in org_repos}
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pixi run --manifest-path monitor/pixi.toml pytest tests/test_discover.py -q`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add monitor/discover.py monitor/tests/test_discover.py
git commit -m "monitor: discover workflow repos in the org and diff against the registry"
```

---

### Task 7: Live smoke test and first real run

**Files:**
- Create: `monitor/tests/test_live.py`

- [ ] **Step 1: Write the live test**

`monitor/tests/test_live.py`:
```python
import os

import pytest

from collect import collect_workflow, fetch_catalog
from gh import GitHubClient
from metadata import load_indicators

TOKEN = os.environ.get("MONITOR_PAT") or os.environ.get("GITHUB_TOKEN")

pytestmark = pytest.mark.skipif(not TOKEN, reason="needs MONITOR_PAT or GITHUB_TOKEN")


def test_live_wt_ndvi_has_metadata_and_desktop_version():
    client = GitHubClient()
    catalog = fetch_catalog(client.session)
    vocab = load_indicators(os.path.join(os.path.dirname(__file__), "..", "indicators.yaml"))
    entry = {"id": "wt-ndvi", "repo": "wildlife-dynamics/wt-ndvi", "epic": "https://github.com/wildlife-dynamics/ndvi/issues/22"}
    record = collect_workflow(entry, client, catalog, vocab)
    assert record["errors"] == []
    assert record["metadata_missing"] is False
    assert record["name"] == "NDVI Workflow"
    assert record["indicators"] == ["ndvi"]
    assert record["desktop_version"]
    assert record["web_version"]
    assert record["epic"]["type"] == "Workflow"
```

- [ ] **Step 2: Run it with a real token**

Run: `MONITOR_PAT=$(gh auth token) pixi run --manifest-path monitor/pixi.toml pytest tests/test_live.py -q -rs`
Expected: 1 passed. If the epic lookup fails with a permissions error, the `gh` token lacks `read:project` — run `gh auth refresh -s read:project` and retry. If `desktop_version` is None, print the record and check the catalog `version_file_path` matches what is on `main`.

- [ ] **Step 3: Produce the first real snapshot**

Run:
```bash
MONITOR_PAT=$(gh auth token) pixi run --manifest-path monitor/pixi.toml python discover.py --json > /Users/yunwu/.claude/jobs/249a07d8/tmp/unreg.json
MONITOR_PAT=$(gh auth token) pixi run --manifest-path monitor/pixi.toml python collect.py --unregistered /Users/yunwu/.claude/jobs/249a07d8/tmp/unreg.json
python3 -c "import json; d=json.load(open('monitor/build/data.json')); [print(w['id'], w['epic'] and w['epic']['status'], w['desktop_version'], w['web_version'], w['ci_status'], w['errors']) for w in d['workflows']]"
```
`collect.py` defaults `--out` to `monitor/build/data.json` relative to its own location, so the working directory pixi picks does not matter; only the `--unregistered` path must be absolute.
Expected: 15 rows; wt-ndvi shows a status, both versions, and no errors. Rows for repos without `test.yml` show `None` CI without an error. Note any surprising errors in the commit message body but do not block on them unless they indicate a bug in the collector.

- [ ] **Step 4: Add `monitor/build/` to `.gitignore` and commit**

Append to `.gitignore`:
```
monitor/build/
```

```bash
git add .gitignore monitor/tests/test_live.py
git commit -m "monitor: live smoke test against wt-ndvi; ignore build output"
```

---

### Task 8: The page

**Files:**
- Create: `monitor/index.html`, `monitor/sample-data.json`

**Interfaces:**
- Consumes: `data.json` shape from Task 5 (`generated_at`, `unregistered`, `workflows[]`).

- [ ] **Step 1: Write the sample fixture**

`monitor/sample-data.json`:
```json
{
  "generated_at": "2026-09-10T12:00:00Z",
  "unregistered": [{"repo": "wildlife-dynamics/mnc-patrol-effort", "visibility": "public"}],
  "workflows": [
    {
      "id": "wt-ndvi", "repo": "wildlife-dynamics/wt-ndvi",
      "epic": {"url": "https://github.com/wildlife-dynamics/ndvi/issues/22", "title": "NDVI", "state": "CLOSED", "type": "Workflow",
               "status": "Done", "priority": "P1", "size": "M",
               "projects": [{"number": 9, "title": "Wildlife Dynamics", "url": "https://github.com/orgs/wildlife-dynamics/projects/9"}],
               "sub_issues": [{"number": 30, "repo": "wildlife-dynamics/wt-ndvi", "title": "Baseline comparison off by one month", "state": "OPEN", "type": "Bug", "url": "https://github.com/wildlife-dynamics/wt-ndvi/issues/30"},
                              {"number": 12, "repo": "wildlife-dynamics/ecoscope", "title": "GEE export helper", "state": "CLOSED", "type": "Feature", "url": "https://github.com/wildlife-dynamics/ecoscope/issues/12"}],
               "sub_issues_total": 2, "sub_issues_completed": 1},
      "visibility": "public", "archived": false,
      "name": "NDVI Workflow", "description": "Monitor vegetation health using satellite-derived NDVI data.",
      "maintainers": [{"name": "Yun Wu", "email": "yun@wildlifedynamics.com", "role": "owner"}],
      "outputs": [{"name": "NDVI Dashboard", "type": "dashboard", "description": "NDVI trends and maps per region.",
                   "components": [{"name": "NDVI Map", "type": "map", "description": "Mean NDVI per region of interest", "indicators": ["ndvi"]},
                                  {"name": "NDVI Trend", "type": "plot", "description": "Monthly NDVI against baseline", "indicators": ["ndvi"]}]},
                  {"name": "NDVI Data", "type": "file", "description": "Calculated NDVI values", "components": []}],
      "indicators": ["ndvi"], "unknown_indicators": [],
      "metadata_missing": false, "spec_missing": false,
      "desktop_version": "1.0.1", "web_version": "1.0.0",
      "ci_status": "success", "ci_url": "https://github.com/wildlife-dynamics/wt-ndvi/actions",
      "open_issue_count": 1,
      "issues": [{"number": 30, "title": "Baseline comparison off by one month", "url": "https://github.com/wildlife-dynamics/wt-ndvi/issues/30", "labels": ["bug"], "created_at": "2026-08-30T00:00:00Z", "assignee": "Yun-Wu"}],
      "errors": []
    },
    {
      "id": "mt-patrols", "repo": "wildlife-dynamics/mt-patrols",
      "epic": {"url": "https://github.com/wildlife-dynamics/mt-patrols/issues/4", "title": "Mara Triangle Patrol Workflow", "state": "OPEN", "type": "Workflow",
               "status": "Ready", "priority": "P2", "size": null,
               "projects": [{"number": 9, "title": "Wildlife Dynamics", "url": "https://github.com/orgs/wildlife-dynamics/projects/9"}, {"number": 22, "title": "Mara North", "url": "https://github.com/orgs/wildlife-dynamics/projects/22"}],
               "sub_issues": [{"number": 741, "repo": "wildlife-dynamics/ecoscope", "title": "Patrol distance discrepancy", "state": "OPEN", "type": "Bug", "url": "https://github.com/wildlife-dynamics/ecoscope/issues/741"}],
               "sub_issues_total": 1, "sub_issues_completed": 0},
      "visibility": "public", "archived": false,
      "name": "mt-patrols", "description": "", "maintainers": [],
      "outputs": [], "indicators": [], "unknown_indicators": [],
      "metadata_missing": true, "spec_missing": false,
      "desktop_version": null, "web_version": null,
      "ci_status": null, "ci_url": null,
      "open_issue_count": 0, "issues": [],
      "errors": []
    },
    {
      "id": "wt-bh-anti-poaching", "repo": "wildlife-dynamics/wt-bh-anti-poaching",
      "epic": null,
      "visibility": "private", "archived": false,
      "name": "Anti-poaching patrols", "description": "Patrol coverage for Bahari Hai.", "maintainers": [],
      "outputs": [{"name": "Patrol Report", "type": "report", "description": "Monthly report",
                   "components": [{"name": "Last visited map", "type": "map", "description": "Map of the last-visited patrol areas", "indicators": ["patrol-effort"]}]}],
      "indicators": ["patrol-effort"], "unknown_indicators": ["ranger morale"],
      "metadata_missing": false, "spec_missing": false,
      "desktop_version": null, "web_version": null,
      "ci_status": "failure", "ci_url": "https://github.com/wildlife-dynamics/wt-bh-anti-poaching/actions",
      "open_issue_count": 0, "issues": [],
      "errors": ["epic: epic not found: https://github.com/wildlife-dynamics/wt-bh-anti-poaching/issues/99"]
    }
  ]
}
```

- [ ] **Step 2: Write the page**

`monitor/index.html`:
```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ecoscope Workflow Monitor</title>
<style>
  :root {
    --bg: #fafaf9; --fg: #1c1917; --muted: #78716c; --line: #e7e5e4; --card: #ffffff; --accent: #0f766e;
    --ok: #15803d; --warn: #b45309; --bad: #b91c1c; --info: #1d4ed8; --chip: #f5f5f4;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #0c0a09; --fg: #e7e5e4; --muted: #a8a29e; --line: #292524; --card: #1c1917; --accent: #2dd4bf;
            --ok: #4ade80; --warn: #fbbf24; --bad: #f87171; --info: #93c5fd; --chip: #292524; }
  }
  * { box-sizing: border-box; }
  body { margin: 0; padding-block: 16px; padding-inline: 16px; background: var(--bg); color: var(--fg);
         font: 14px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  a { color: var(--accent); }
  header { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: baseline; margin-bottom: 12px; }
  header h1 { font-size: 20px; margin: 0; }
  header .meta { color: var(--muted); }
  header .meta.stale { color: var(--warn); }
  nav.tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--line); margin: 8px 0 12px; }
  nav.tabs button { background: none; border: 0; border-bottom: 2px solid transparent; color: var(--muted); padding: 8px 12px; cursor: pointer; font: inherit; }
  nav.tabs button.active { color: var(--fg); border-bottom-color: var(--accent); }
  .filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
  .filters input, .filters select { font: inherit; padding: 6px 8px; border: 1px solid var(--line); border-radius: 6px; background: var(--card); color: var(--fg); }
  .filters input { flex: 1 1 200px; min-width: 0; }
  .tablewrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; background: var(--card); }
  table { border-collapse: collapse; width: 100%; min-width: 900px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
  th { font-weight: 600; white-space: nowrap; cursor: pointer; user-select: none; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .03em; }
  th.sorted::after { content: " ▲"; } th.sorted.desc::after { content: " ▼"; }
  tr.row { cursor: pointer; } tr.row:hover td { background: color-mix(in srgb, var(--accent) 6%, transparent); }
  tr.detail td { background: color-mix(in srgb, var(--chip) 60%, transparent); cursor: default; }
  .chip { display: inline-block; padding: 1px 7px; border-radius: 999px; background: var(--chip); font-size: 12px; margin: 1px 2px 1px 0; white-space: nowrap; }
  .chip.ok { color: var(--ok); } .chip.warn { color: var(--warn); } .chip.bad { color: var(--bad); } .chip.info { color: var(--info); }
  .badge { font-size: 11px; color: var(--warn); margin-left: 4px; }
  .badge.bad { color: var(--bad); }
  .muted { color: var(--muted); }
  .detail { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; padding: 4px 0; }
  .detail h4 { margin: 0 0 6px; font-size: 13px; text-transform: uppercase; letter-spacing: .03em; color: var(--muted); }
  .detail ul { margin: 0; padding-left: 18px; }
  .detail li { margin: 2px 0; }
  .empty { padding: 24px; color: var(--muted); text-align: center; }
  details.unreg { margin-top: 16px; }
  details.unreg summary { cursor: pointer; color: var(--muted); }
  .count { color: var(--muted); font-size: 12px; margin-bottom: 6px; }
  @media (max-width: 640px) { header h1 { font-size: 18px; } }
</style>
</head>
<body>
<header>
  <h1>Ecoscope Workflow Monitor</h1>
  <span class="meta" id="generated">loading…</span>
  <span class="meta">
    <a href="https://github.com/orgs/wildlife-dynamics/projects/9" target="_blank" rel="noopener">Project</a> ·
    <a href="https://github.com/wildlife-dynamics/ecoscope-hub/edit/main/monitor/registry.yaml" target="_blank" rel="noopener">Edit registry</a> ·
    <a href="https://github.com/wildlife-dynamics/ecoscope-hub/actions/workflows/monitor.yml" target="_blank" rel="noopener">Rebuild</a>
  </span>
</header>

<nav class="tabs">
  <button data-tab="workflows" class="active">Workflows</button>
  <button data-tab="outputs">Outputs</button>
</nav>

<section id="tab-workflows">
  <div class="filters">
    <input id="wf-q" type="search" placeholder="Search id, name, indicators…">
    <select id="wf-project"><option value="">All projects</option></select>
    <select id="wf-status"><option value="">All statuses</option></select>
    <select id="wf-priority"><option value="">All priorities</option></select>
    <select id="wf-otype"><option value="">All output types</option></select>
    <select id="wf-avail">
      <option value="">Any availability</option>
      <option value="desktop">On Desktop</option>
      <option value="web">On Web</option>
      <option value="none">Not available</option>
    </select>
  </div>
  <div class="count" id="wf-count"></div>
  <div class="tablewrap"><table id="wf-table"><thead><tr>
    <th data-key="priority">Priority</th><th data-key="name">Workflow</th><th data-key="projects">Projects</th>
    <th data-key="status">Status</th><th data-key="epic">Epic</th><th data-key="desktop">Desktop</th><th data-key="web">Web</th>
    <th data-key="outputs">Outputs</th><th data-key="indicators">Indicators</th><th data-key="ci">CI</th><th data-key="open">Open work</th>
  </tr></thead><tbody></tbody></table></div>
</section>

<section id="tab-outputs" hidden>
  <div class="filters">
    <input id="out-q" type="search" placeholder="Search component name or description…">
    <select id="out-indicator"><option value="">All indicators</option></select>
    <select id="out-ctype"><option value="">All component types</option></select>
    <select id="out-dtype"><option value="">All deliverable types</option></select>
    <select id="out-project"><option value="">All projects</option></select>
  </div>
  <div class="count" id="out-count"></div>
  <div class="tablewrap"><table id="out-table"><thead><tr>
    <th>Workflow</th><th>Deliverable</th><th>Deliverable type</th><th>Component</th><th>Component type</th><th>Description</th><th>Indicators</th>
  </tr></thead><tbody></tbody></table></div>
</section>

<details class="unreg" id="unreg"><summary>Unregistered workflow repos</summary><ul></ul></details>

<script>
(function () {
  const DATA_URL = new URLSearchParams(location.search).get('data') || 'data.json';
  const PRIORITY_ORDER = ['P0', 'P1', 'P2', 'P3'];
  const STATUS_ORDER = ['In progress', 'In review', 'Ready', 'Backlog', 'Done'];
  const $ = (s, r = document) => r.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const link = (href, text) => href ? `<a href="${esc(href)}" target="_blank" rel="noopener">${esc(text)}</a>` : esc(text);
  const chip = (text, cls = '') => text ? `<span class="chip ${cls}">${esc(text)}</span>` : '';
  const state = { workflows: [], unregistered: [], sort: { key: 'priority', desc: false }, open: null };

  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    return Object.fromEntries(p.entries());
  }
  function writeHash(obj) {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(obj)) if (v) p.set(k, v);
    history.replaceState(null, '', '#' + p.toString());
  }
  function currentFilters() {
    return {
      tab: $('nav.tabs button.active').dataset.tab,
      q: $('#wf-q').value, project: $('#wf-project').value, status: $('#wf-status').value,
      priority: $('#wf-priority').value, otype: $('#wf-otype').value, avail: $('#wf-avail').value,
      oq: $('#out-q').value, oind: $('#out-indicator').value, octype: $('#out-ctype').value,
      odtype: $('#out-dtype').value, oproject: $('#out-project').value,
      open: state.open || '',
    };
  }

  function fillSelect(sel, values) {
    const keep = sel.value;
    for (const v of values) { const o = document.createElement('option'); o.value = v; o.textContent = v; sel.appendChild(o); }
    sel.value = keep;
  }
  function uniq(list) { return [...new Set(list.filter(Boolean))]; }
  function projectsOf(w) { return (w.epic?.projects || []).map(p => p.title); }
  function openWork(w) {
    const subs = (w.epic?.sub_issues || []).filter(s => s.state === 'OPEN').length;
    return subs + (w.open_issue_count || 0);
  }
  function ciClass(c) { return c === 'success' ? 'ok' : c === 'failure' ? 'bad' : c ? 'warn' : ''; }
  function statusClass(s) { return s === 'Done' ? 'ok' : s === 'In progress' || s === 'In review' ? 'info' : s === 'Ready' ? 'warn' : ''; }
  function priorityClass(p) { return p === 'P0' ? 'bad' : p === 'P1' ? 'warn' : ''; }
  function rank(list, v) { const i = list.indexOf(v); return i < 0 ? list.length : i; }

  function badges(w) {
    const out = [];
    if (w.spec_missing) out.push('<span class="badge bad">no spec.yaml</span>');
    else if (w.metadata_missing) out.push('<span class="badge">no metadata</span>');
    if (!w.epic) out.push('<span class="badge">no epic</span>');
    if (w.visibility === 'private') out.push('<span class="badge">private</span>');
    if (w.archived) out.push('<span class="badge">archived</span>');
    if (w.unknown_indicators?.length) out.push(`<span class="badge" title="${esc(w.unknown_indicators.join(', '))}">unknown indicators</span>`);
    if (w.errors?.length) out.push(`<span class="badge bad" title="${esc(w.errors.join('\n'))}">${w.errors.length} error${w.errors.length > 1 ? 's' : ''}</span>`);
    return out.join('');
  }

  function sortKey(w, key) {
    switch (key) {
      case 'priority': return [rank(PRIORITY_ORDER, w.epic?.priority), rank(STATUS_ORDER, w.epic?.status), w.name.toLowerCase()];
      case 'name': return [w.name.toLowerCase()];
      case 'projects': return [projectsOf(w).join(',').toLowerCase()];
      case 'status': return [rank(STATUS_ORDER, w.epic?.status), w.name.toLowerCase()];
      case 'epic': return [w.epic?.state || 'zz'];
      case 'desktop': return [w.desktop_version || 'zz'];
      case 'web': return [w.web_version || 'zz'];
      case 'outputs': return [w.outputs.map(o => o.type).join(',')];
      case 'indicators': return [w.indicators.join(',')];
      case 'ci': return [w.ci_status || 'zz'];
      case 'open': return [-openWork(w)];
      default: return [''];
    }
  }
  function compare(a, b) {
    const ka = sortKey(a, state.sort.key), kb = sortKey(b, state.sort.key);
    for (let i = 0; i < ka.length; i++) { if (ka[i] < kb[i]) return state.sort.desc ? 1 : -1; if (ka[i] > kb[i]) return state.sort.desc ? -1 : 1; }
    return 0;
  }

  function filteredWorkflows() {
    const f = currentFilters(); const q = f.q.trim().toLowerCase();
    return state.workflows.filter(w => {
      if (q && !(w.id + ' ' + w.name + ' ' + w.indicators.join(' ')).toLowerCase().includes(q)) return false;
      if (f.project && !projectsOf(w).includes(f.project)) return false;
      if (f.status && (w.epic?.status || '') !== f.status) return false;
      if (f.priority && (w.epic?.priority || '') !== f.priority) return false;
      if (f.otype && !w.outputs.some(o => o.type === f.otype)) return false;
      if (f.avail === 'desktop' && !w.desktop_version) return false;
      if (f.avail === 'web' && !w.web_version) return false;
      if (f.avail === 'none' && (w.desktop_version || w.web_version)) return false;
      return true;
    }).sort(compare);
  }

  function renderWorkflows() {
    const rows = filteredWorkflows();
    $('#wf-count').textContent = `${rows.length} of ${state.workflows.length} workflows`;
    const tbody = $('#wf-table tbody');
    if (!rows.length) { tbody.innerHTML = '<tr><td colspan="11" class="empty">No workflows match.</td></tr>'; return; }
    tbody.innerHTML = rows.map(w => {
      const e = w.epic;
      const row = `<tr class="row" data-id="${esc(w.id)}">
        <td>${chip(e?.priority, priorityClass(e?.priority)) || '<span class="muted">—</span>'}</td>
        <td><strong>${esc(w.name)}</strong> <span class="muted">${esc(w.id !== w.name ? w.id : '')}</span>${badges(w)}</td>
        <td>${projectsOf(w).map(p => chip(p)).join('') || '<span class="muted">—</span>'}</td>
        <td>${chip(e?.status, statusClass(e?.status)) || '<span class="muted">—</span>'}</td>
        <td>${e ? link(e.url, '#' + e.url.split('/').pop()) + (e.state === 'CLOSED' ? ' <span class="muted">closed</span>' : '') : '<span class="muted">—</span>'}</td>
        <td>${w.desktop_version ? chip('v' + w.desktop_version, 'ok') : '<span class="muted">—</span>'}</td>
        <td>${w.web_version ? chip('v' + w.web_version, 'ok') : '<span class="muted">—</span>'}</td>
        <td>${uniq(w.outputs.map(o => o.type)).map(t => chip(t)).join('') || '<span class="muted">—</span>'}</td>
        <td>${w.indicators.map(i => chip(i, 'info')).join('') || '<span class="muted">—</span>'}</td>
        <td>${w.ci_status ? link(w.ci_url, w.ci_status).replace('<a ', `<a class="chip ${ciClass(w.ci_status)}" `) : '<span class="muted">—</span>'}</td>
        <td>${openWork(w)}</td>
      </tr>`;
      return row + (state.open === w.id ? `<tr class="detail"><td colspan="11">${renderDetail(w)}</td></tr>` : '');
    }).join('');
    for (const th of document.querySelectorAll('#wf-table th')) {
      th.classList.toggle('sorted', th.dataset.key === state.sort.key);
      th.classList.toggle('desc', th.dataset.key === state.sort.key && state.sort.desc);
    }
  }

  function age(iso) { const d = (Date.now() - Date.parse(iso)) / 864e5; return d < 1 ? 'today' : `${Math.floor(d)}d`; }
  function renderDetail(w) {
    const e = w.epic;
    const subs = (e?.sub_issues || []).slice().sort((a, b) => (a.state === b.state ? 0 : a.state === 'OPEN' ? -1 : 1));
    const epicBlock = e ? `<p>${link(e.url, e.title)} <span class="muted">· ${esc(e.state.toLowerCase())} · ${esc(e.type || 'untyped')}${e.size ? ' · size ' + esc(e.size) : ''} · ${e.sub_issues_completed}/${e.sub_issues_total} sub-issues done</span></p>` : '<p class="muted">No epic linked.</p>';
    const repoLink = w.repo ? link('https://github.com/' + w.repo, w.repo) : '<span class="muted">no repo</span>';
    const maint = w.maintainers.map(m => `${esc(m.name || m.email || '?')}${m.role ? ' <span class="muted">(' + esc(m.role) + ')</span>' : ''}`).join(', ');
    const outputs = w.outputs.map(o => `<li><strong>${esc(o.name)}</strong> ${chip(o.type)}${o.description ? ' <span class="muted">' + esc(o.description) + '</span>' : ''}
      ${o.components.length ? '<ul>' + o.components.map(c => `<li>${esc(c.name)} ${chip(c.type)} ${c.indicators.map(i => chip(i, 'info')).join('')}${c.description ? ' <span class="muted">' + esc(c.description) + '</span>' : ''}</li>`).join('') + '</ul>' : ''}</li>`).join('');
    const tracked = subs.map(s => `<li>${link(s.url, s.title)} <span class="muted">· ${esc(s.repo)} · ${esc(s.type || '')} · ${esc(s.state.toLowerCase())}</span></li>`).join('');
    const issues = w.issues.map(i => `<li>${link(i.url, '#' + i.number + ' ' + i.title)} ${i.labels.map(l => chip(l)).join('')} <span class="muted">· ${age(i.created_at)}${i.assignee ? ' · ' + esc(i.assignee) : ''}</span></li>`).join('');
    const errors = w.errors.length ? `<div><h4>Errors</h4><ul>${w.errors.map(x => `<li class="badge bad">${esc(x)}</li>`).join('')}</ul></div>` : '';
    return `<div class="detail">
      <div><h4>Epic</h4>${epicBlock}<h4>Repo</h4><p>${repoLink}${w.ci_url ? ' · ' + link(w.ci_url, 'last CI run') : ''} · <a href="https://github.com/wildlife-dynamics/ecoscope-hub/edit/main/monitor/registry.yaml" target="_blank" rel="noopener">edit in registry</a></p>
        ${w.description ? '<h4>Description</h4><p>' + esc(w.description) + '</p>' : ''}${maint ? '<h4>Maintainers</h4><p>' + maint + '</p>' : ''}</div>
      <div><h4>Outputs</h4>${outputs ? '<ul>' + outputs + '</ul>' : '<p class="muted">None declared.</p>'}</div>
      <div><h4>Tracked work (${subs.filter(s => s.state === 'OPEN').length} open)</h4>${tracked ? '<ul>' + tracked + '</ul>' : '<p class="muted">No sub-issues.</p>'}
        <h4>Repo issues (${w.issues.length})</h4>${issues ? '<ul>' + issues + '</ul>' : '<p class="muted">None open.</p>'}${errors}</div>
    </div>`;
  }

  function componentRows() {
    const rows = [];
    for (const w of state.workflows) for (const o of w.outputs) for (const c of o.components)
      rows.push({ w, o, c });
    return rows;
  }
  function renderOutputs() {
    const f = currentFilters(); const q = f.oq.trim().toLowerCase();
    const all = componentRows();
    const rows = all.filter(({ w, o, c }) => {
      if (q && !(c.name + ' ' + c.description).toLowerCase().includes(q)) return false;
      if (f.oind && !c.indicators.includes(f.oind)) return false;
      if (f.octype && c.type !== f.octype) return false;
      if (f.odtype && o.type !== f.odtype) return false;
      if (f.oproject && !projectsOf(w).includes(f.oproject)) return false;
      return true;
    });
    $('#out-count').textContent = `${rows.length} of ${all.length} components`;
    const tbody = $('#out-table tbody');
    if (!rows.length) { tbody.innerHTML = '<tr><td colspan="7" class="empty">No components match.</td></tr>'; return; }
    tbody.innerHTML = rows.map(({ w, o, c }) => `<tr>
      <td><a href="#" data-open="${esc(w.id)}">${esc(w.name)}</a></td><td>${esc(o.name)}</td><td>${chip(o.type)}</td>
      <td>${esc(c.name)}</td><td>${chip(c.type)}</td><td>${esc(c.description)}</td><td>${c.indicators.map(i => chip(i, 'info')).join('')}</td>
    </tr>`).join('');
  }

  function renderUnregistered() {
    const ul = $('#unreg ul');
    $('#unreg summary').textContent = `Unregistered workflow repos (${state.unregistered.length})`;
    ul.innerHTML = state.unregistered.map(u => `<li>${link('https://github.com/' + u.repo, u.repo)} <span class="muted">${esc(u.visibility)}</span></li>`).join('') || '<li class="muted">None.</li>';
  }

  function showTab(name) {
    for (const b of document.querySelectorAll('nav.tabs button')) b.classList.toggle('active', b.dataset.tab === name);
    $('#tab-workflows').hidden = name !== 'workflows';
    $('#tab-outputs').hidden = name !== 'outputs';
  }
  function renderAll() { renderWorkflows(); renderOutputs(); writeHash(currentFilters()); }

  function init(data) {
    state.workflows = data.workflows || [];
    state.unregistered = data.unregistered || [];
    const ageMs = Date.now() - Date.parse(data.generated_at);
    const gen = $('#generated');
    gen.textContent = `generated ${Math.round(ageMs / 6e4)} min ago (${data.generated_at})`;
    gen.classList.toggle('stale', ageMs > 12 * 36e5);

    const projects = uniq(state.workflows.flatMap(projectsOf)).sort();
    fillSelect($('#wf-project'), projects); fillSelect($('#out-project'), projects);
    fillSelect($('#wf-status'), uniq(state.workflows.map(w => w.epic?.status)).sort((a, b) => rank(STATUS_ORDER, a) - rank(STATUS_ORDER, b)));
    fillSelect($('#wf-priority'), uniq(state.workflows.map(w => w.epic?.priority)).sort());
    fillSelect($('#wf-otype'), uniq(state.workflows.flatMap(w => w.outputs.map(o => o.type))).sort());
    fillSelect($('#out-dtype'), uniq(state.workflows.flatMap(w => w.outputs.map(o => o.type))).sort());
    fillSelect($('#out-ctype'), uniq(componentRows().map(r => r.c.type)).sort());
    fillSelect($('#out-indicator'), uniq(state.workflows.flatMap(w => w.indicators)).sort());

    const h = readHash();
    const map = { q: '#wf-q', project: '#wf-project', status: '#wf-status', priority: '#wf-priority', otype: '#wf-otype', avail: '#wf-avail',
                  oq: '#out-q', oind: '#out-indicator', octype: '#out-ctype', odtype: '#out-dtype', oproject: '#out-project' };
    for (const [k, sel] of Object.entries(map)) if (h[k] != null) $(sel).value = h[k];
    state.open = h.open || null;
    showTab(h.tab === 'outputs' ? 'outputs' : 'workflows');

    for (const sel of Object.values(map)) $(sel).addEventListener('input', renderAll);
    for (const b of document.querySelectorAll('nav.tabs button')) b.addEventListener('click', () => { showTab(b.dataset.tab); writeHash(currentFilters()); });
    for (const th of document.querySelectorAll('#wf-table th')) th.addEventListener('click', () => {
      state.sort = { key: th.dataset.key, desc: state.sort.key === th.dataset.key ? !state.sort.desc : false }; renderWorkflows();
    });
    $('#wf-table tbody').addEventListener('click', ev => {
      if (ev.target.closest('a')) return;
      const tr = ev.target.closest('tr.row'); if (!tr) return;
      state.open = state.open === tr.dataset.id ? null : tr.dataset.id; renderAll();
    });
    $('#out-table tbody').addEventListener('click', ev => {
      const a = ev.target.closest('a[data-open]'); if (!a) return;
      ev.preventDefault(); state.open = a.dataset.open; showTab('workflows'); renderAll();
      document.querySelector(`tr.row[data-id="${CSS.escape(state.open)}"]`)?.scrollIntoView({ block: 'center' });
    });
    renderUnregistered();
    renderAll();
  }

  fetch(DATA_URL, { cache: 'no-cache' })
    .then(r => { if (!r.ok) throw new Error(r.status + ' ' + r.statusText); return r.json(); })
    .then(init)
    .catch(err => {
      $('#generated').textContent = 'failed to load data.json: ' + err.message;
      $('#generated').classList.add('stale');
      $('#wf-table tbody').innerHTML = '<tr><td colspan="11" class="empty">Could not load the snapshot. Check the latest monitor run in Actions.</td></tr>';
    });
})();
</script>
</body>
</html>
```

- [ ] **Step 3: Check the page locally against the sample and the real snapshot**

Run (from `monitor/`): `pixi run --manifest-path monitor/pixi.toml python -m http.server 8765 --directory monitor` in the background, then open `http://localhost:8765/index.html?data=sample-data.json` and `http://localhost:8765/index.html?data=build/data.json`.

Checklist:
- Header shows the generated time; the sample's 2026-09-10 stamp renders amber (stale) once more than 12 h old.
- Rows sort P1 (wt-ndvi) before P2 (mt-patrols) before no-priority (wt-bh-anti-poaching).
- Badges: mt-patrols shows "no metadata"; wt-bh-anti-poaching shows "no epic", "private", "unknown indicators", "1 error".
- Clicking wt-ndvi opens the drill-down with epic, outputs tree, 1 open tracked issue, 1 repo issue; the URL hash contains `open=wt-ndvi`; reload keeps it open.
- Outputs tab: filter component type = map → 2 rows; search "last-visited" → 1 row; clicking its workflow jumps back to the drill-down.
- Availability filter "On Web" → only wt-ndvi.
- Narrow the window to 400px: no horizontal page scroll; the table scrolls inside its container.
- Stop the server when done.

If any check fails, fix `index.html` and re-check before committing.

- [ ] **Step 4: Commit**

```bash
git add monitor/index.html monitor/sample-data.json
git commit -m "monitor: single-file page with workflows and outputs tabs"
```

---

### Task 9: GitHub Actions workflow, README, and Pages enablement

**Files:**
- Create: `.github/workflows/monitor.yml`, `monitor/README.md`
- Modify: `README.md` (add one "Workflow monitor" line pointing at `monitor/README.md`)

- [ ] **Step 1: Write the workflow**

`.github/workflows/monitor.yml`:
```yaml
name: Workflow monitor

on:
  schedule:
    - cron: "17 */6 * * *"
  push:
    branches: [main]
    paths:
      - "monitor/**"
      - ".github/workflows/monitor.yml"
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: workflow-monitor
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    env:
      MONITOR_PAT: ${{ secrets.MONITOR_PAT }}
      GITHUB_TOKEN: ${{ github.token }}
    steps:
      - uses: actions/checkout@v4
      - uses: prefix-dev/setup-pixi@v0.8.10
        with:
          pixi-version: v0.57.0
          manifest-path: monitor/pixi.toml
      - name: Test
        run: pixi run --manifest-path monitor/pixi.toml pytest -q tests --ignore=tests/test_live.py
      - name: Discover unregistered workflow repos
        run: pixi run --manifest-path monitor/pixi.toml python discover.py --json > "$GITHUB_WORKSPACE/unregistered.json"
      - name: Collect snapshot
        run: pixi run --manifest-path monitor/pixi.toml python collect.py --unregistered "$GITHUB_WORKSPACE/unregistered.json"
      - name: Assemble site
        run: cp monitor/index.html monitor/build/index.html
      - uses: actions/upload-pages-artifact@v3
        with:
          path: monitor/build

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

Notes: `collect.py` writes to `monitor/build/data.json` by default (relative to its own file), so it does not matter which working directory pixi uses; the `--unregistered` path is absolute for the same reason, and the shell redirect in the Discover step runs from the repo root. `GITHUB_TOKEN` is set so runs without `MONITOR_PAT` still read public repos; epics then record errors until the secret is added.

- [ ] **Step 2: Write `monitor/README.md`**

```markdown
# Ecoscope Workflow Monitor

A GitHub Pages site listing every registered ecoscope workflow with its epic's status and
priority (from the Wildlife Dynamics GitHub Project), availability on Desktop and Web, outputs
and indicators (from each repo's `spec.yaml` metadata), CI state, and open work.

Design: `docs/superpowers/specs/2026-09-10-workflow-monitor-design.md`.

## Add or retire a workflow

Edit `registry.yaml`. Each entry is `id`, `repo`, and the `epic` issue URL. Status, priority,
size, and project membership are managed on the epic in GitHub Projects, not here. Committing
to `main` rebuilds the site.

To find workflow repos that are not registered yet:

    pixi run discover            # report only
    pixi run discover -- --add   # append stubs (fill in the epic afterwards)

## Run locally

    export MONITOR_PAT=$(gh auth token)      # needs read:project for epic fields
    pixi run discover -- --json > build/unregistered.json
    pixi run collect -- --unregistered build/unregistered.json
    python -m http.server 8765               # then open http://localhost:8765/index.html

`index.html?data=sample-data.json` renders the committed fixture without a token.

## Tests

    pixi run test                            # unit tests, no network
    MONITOR_PAT=$(gh auth token) pixi run test -- tests/test_live.py   # live smoke test

## CI secret

The Action needs a repo secret `MONITOR_PAT`: a fine-grained personal access token for the
`wildlife-dynamics` org with **Organization permissions → Projects: read** and **Repository
permissions → Contents, Issues, Actions, Metadata: read** on all repos. Without it, epics show
errors and private repos do not resolve.

## Indicators

`indicators.yaml` is the canonical vocabulary. Add an id with a label and aliases when a spec
uses an indicator the monitor flags as unknown.
```

- [ ] **Step 3: Add a pointer in the root README**

Insert after the first paragraph of `README.md`:
```markdown
> **Workflow monitor:** the fleet status page lives in [`monitor/`](monitor/README.md).
```

- [ ] **Step 4: Run the unit suite one last time**

Run: `pixi run --manifest-path monitor/pixi.toml pytest -q tests --ignore=tests/test_live.py`
Expected: all passed.

- [ ] **Step 5: Commit and push**

```bash
git add .github/workflows/monitor.yml monitor/README.md README.md
git commit -m "monitor: GitHub Actions build + Pages deploy, README"
git push -u origin HEAD
```

- [ ] **Step 6: Enable Pages and the secret (one-time, needs repo admin)**

These cannot be done from the plan runner without admin rights; do them, or hand them to the user:

```bash
# Pages source = GitHub Actions
gh api -X POST repos/wildlife-dynamics/ecoscope-hub/pages -f build_type=workflow
# PAT: create at https://github.com/settings/personal-access-tokens/new (resource owner: wildlife-dynamics)
gh secret set MONITOR_PAT --repo wildlife-dynamics/ecoscope-hub
```

Then open a PR via the `pr` skill. After merge, run the workflow once by hand
(`gh workflow run monitor.yml --repo wildlife-dynamics/ecoscope-hub`) and open the URL printed
by the deploy job. Confirm wt-ndvi shows status, both versions, and its epic link.

---

## Self-review

**Spec coverage**
- Registry with id/repo/epic + validation → Task 1. Epic read (type check, WD project first, projects list, sub-issue pagination) → Task 4. Indicator vocabulary + flat/nested outputs + unknown flags → Task 3. Visibility rule, catalog, Desktop/Web versions, CI, repo issues excluding PRs, per-repo error isolation, `--only`, `--unregistered` → Task 5. Discovery three groups, `--add`, `--json` → Task 6. Live smoke test → Task 7. Page (header links, tabs, filters in hash, sort by priority then status, badges, drill-down with two issue lists, outputs index, unregistered panel, error state, 400px) → Task 8. Action (cron/push/dispatch, tests before deploy, PAT, Pages) → Task 9.
- Not covered by a task on purpose: `monitor-data` history branch and in-page editing (spec: out of scope).

**Type consistency**
- `fetch_epic` returns `(record, errors)`; `collect_workflow` unpacks it that way. `load_registry` entries always carry `id`, `repo`, `epic` keys; `discover.diff` and `collect` rely on `.get("repo")`. `fetch_catalog` keys are lower-cased `owner/repo`; `collect_workflow` looks up `repo.lower()`. `FakeSession.request` signature matches `GitHubClient._request`'s call (`headers`, `timeout`, `params`, `json`). `data.json` keys used by `index.html` (`epic.projects[].title`, `epic.sub_issues[].state`, `outputs[].components[].indicators`, `open_issue_count`, `unknown_indicators`, `errors`) all exist in `_empty_record` / `fetch_epic`.

**Known judgement calls for the executor**
- Task 9 step 6 needs repo admin rights (Pages source, `MONITOR_PAT` secret). If the executor lacks them, finish everything else and report those two commands for the user.
