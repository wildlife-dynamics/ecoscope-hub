# Ecoscope Workflow Monitor — design

Date: 2026-09-10
Status: approved in conversation, awaiting written review

## Purpose

A single page where the internal team can see every ecoscope workflow the org maintains,
who it is for, where it is in its development lifecycle, whether and at which version it is
available on Ecoscope Desktop and the web platform, what it produces (deliverables,
components, indicators), whether CI is green, and which GitHub issues are open. It must
answer fleet-wide questions such as "which workflows calculate NDVI" and "is there a map of
last-visited patrol areas", and present workflows in priority order.

Audience: the internal team. Delivery: a public GitHub Pages site built on a schedule by a
GitHub Actions workflow in `ecoscope-hub`. The org is on the GitHub **Team** plan, so Pages
cannot be private; this was accepted explicitly. A later hosted version (Cloud Run + IAP with
in-page editing) reuses the collector and page unchanged; it is out of scope here.

## Sources of truth (hybrid model)

| Field group | Owner | Where |
|---|---|---|
| Which workflows exist, organization, lifecycle status, priority rank, notes | ecoscope-hub | `monitor/registry.yaml` |
| Name, description, maintainers, outputs → components → indicators | each workflow repo | `metadata:` block in `spec.yaml` on the default branch |
| Canonical indicator vocabulary | ecoscope-hub | `monitor/indicators.yaml` |
| Desktop availability + version | derived | repo is public **and** listed in the Desktop catalog JSON; version from `VERSION.yaml` on `main` |
| Web availability + version | derived | repo is public **and** has an `ecoscope-web` branch; version from `VERSION.yaml` on that branch |
| Repo visibility, CI status, open issues | derived | GitHub API on every build |

Rule: **a private repo is never shown as available on Desktop or Web**, regardless of catalog
or branch state. Visibility is read from the API on every build.

Nothing collected is stored in git. The snapshot lives only in the deployed Pages artifact and
is regenerated from scratch each run. (A `monitor-data` branch for history is a possible
later addition, not built now.)

## Registry — `monitor/registry.yaml`

```yaml
workflows:
  - id: wt-ndvi                       # unique key; display name fallback when metadata is absent
    repo: wildlife-dynamics/wt-ndvi   # optional when status is "Not Started"
    organization: general             # free text; "general" for non-partner work
    status: Work in Progress          # exactly one of the four values below
    priority: 3                       # integer rank, 1 = most important; optional
    notes: waiting on GEE key         # optional free text
```

Lifecycle status values: `Not Started`, `Work in Progress`, `Review Required`, `Deprecated`.

Validation (build fails on violation): unknown status, duplicate `id`, non-integer priority,
`repo` missing when status is not `Not Started`. Duplicate priorities only warn.

Editing: the page links each row to `registry.yaml` in GitHub's web editor. Committing there
triggers a rebuild. No in-page writes.

## Indicator vocabulary — `monitor/indicators.yaml`

```yaml
indicators:
  ndvi:
    label: NDVI
    description: Normalized Difference Vegetation Index from satellite imagery
    aliases: [NDVI, vegetation index]
  patrol-distance:
    label: Patrol distance
    aliases: [patrol distance, distance patrolled]
```

The collector lower-cases and alias-maps every indicator found in spec metadata to a canonical
id. Unknown indicators are kept verbatim and flagged on the record (`unknown_indicators`).

## Spec metadata — outputs schema

Nested shape (target for all repos):

```yaml
metadata:
  name: NDVI Workflow
  description: ...
  maintainers:
    - {name: ..., email: ..., role: owner}
  outputs:
    - name: NDVI Dashboard
      type: dashboard            # dashboard | report | file
      description: ...
      components:
        - name: NDVI Map
          type: map              # map | plot | table | text | figure
          description: Mean NDVI per region of interest for the selected period
          indicators: [ndvi]
```

Compatibility: the current flat shape in wt-ndvi (top-level `map`/`plot` entries with
`indicators`) is accepted. Top-level entries whose `type` is a component type are attached to
an implicit `dashboard` deliverable named `<workflow name> Dashboard`. `indicators` entries may
be strings or `{name: ...}` objects.

Repos with no `metadata:` block get `metadata_missing: true`; repos with no root `spec.yaml`
get `spec_missing: true`. Both still produce a row.

## Snapshot — `data.json`

```json
{
  "generated_at": "2026-09-10T12:00:00Z",
  "unregistered": [{"repo": "wildlife-dynamics/foo", "visibility": "public"}],
  "workflows": [
    {
      "id": "wt-ndvi", "repo": "wildlife-dynamics/wt-ndvi",
      "organization": "general", "status": "Work in Progress", "priority": 3, "notes": "",
      "visibility": "public", "archived": false,
      "name": "NDVI Workflow", "description": "...", "maintainers": [],
      "outputs": [{"name": "...", "type": "dashboard", "description": "...",
                   "components": [{"name": "...", "type": "map", "description": "...",
                                   "indicators": ["ndvi"]}]}],
      "indicators": ["ndvi"], "unknown_indicators": [],
      "metadata_missing": false, "spec_missing": false,
      "desktop_version": "1.0.0", "web_version": "1.0.0",
      "ci_status": "success", "ci_url": "https://...",
      "open_issue_count": 3,
      "issues": [{"number": 12, "title": "...", "url": "...", "labels": ["bug"],
                  "created_at": "...", "assignee": null}],
      "errors": []
    }
  ]
}
```

`indicators` is the de-duplicated union over all components, for filtering.

## Collector — `monitor/collect.py`

Single file; dependencies `requests` and `pyyaml` from the hub pixi env. Per registry entry,
in order, each step recording an error string and continuing on failure:

1. `GET /repos/{repo}` → visibility, archived, default branch. 404 → error, skip the rest.
2. `spec.yaml` from the default branch → parse `metadata:`; normalise outputs and indicators.
3. Availability (public repos only):
   - Fetch the Desktop catalog JSON once per run
     (`https://storage.googleapis.com/ecoscope-io-storage-public/ecoscope-desktop/hardcoded-template-catalog/workflow_templates.json`).
     If an entry's `url` matches the repo, read `VERSION.yaml` at its `version_file_path` on `main`.
   - If branch `ecoscope-web` exists, read `VERSION.yaml` at the same path on that branch. When
     the repo is not in the catalog, the path is inferred from the generated package dir
     (`<something>-workflow/VERSION.yaml`, discovered via the repo tree).
4. Latest `test.yml` run on the default branch → `conclusion`, `html_url`; null if absent.
5. Open issues (`state=open`, excluding items with `pull_request`) → number, title, url,
   labels, created_at, assignee login.

One HTTP helper handles the token, pagination, and a bounded retry on 403 rate-limit
responses. ~6 calls per repo; well under the 1000/hour limit for an Actions token.

`--registry`, `--out`, `--only <id>` flags for local runs. Exit non-zero only on invalid
registry or an uncaught exception.

## Discovery — `monitor/discover.py`

1. List all non-archived repos in `wildlife-dynamics` (paginated).
2. A repo is a workflow repo iff it has `spec.yaml` at its root.
3. Compare with the registry and report three groups: workflow repos missing from the
   registry, registry entries whose repo is gone or archived, org repos without `spec.yaml`.
4. `--add` appends missing workflow repos to `registry.yaml` as stubs
   (`status: Work in Progress`, `organization: ""`, no priority). Default is report-only.
5. `--json` prints the missing group for the collector, which embeds it as `unregistered`.

## Action — `.github/workflows/monitor.yml`

Triggers: cron every 6 hours; push to `main` touching `monitor/**` or the workflow file;
`workflow_dispatch`.

Steps: checkout → setup-pixi → `pytest monitor/tests` → `discover.py --json` →
`collect.py --out build/data.json` → copy `monitor/index.html` to `build/` →
`actions/upload-pages-artifact` → `actions/deploy-pages`.

Token: `GITHUB_TOKEN` by default. If a repo secret `MONITOR_PAT` (fine-grained; read on
contents, issues, actions, metadata for the org) is present it is used instead so private
repos in the registry resolve. Tests failing or the collector crashing prevents deploy; the
previous site stays up.

## Page — `monitor/index.html`

One file, inline CSS/JS, no dependencies, fetches `data.json` on load. Title "Ecoscope
Workflow Monitor". Light/dark via `prefers-color-scheme`. Works at phone width; tables scroll
horizontally inside their container.

**Header**: title; "generated N minutes ago" (amber when older than 12 h); links to the
Actions page (rebuild) and to `registry.yaml` in GitHub's editor.

**Tabs**: Workflows, Outputs.

**Workflows tab**
- Filter bar: text search over id, name, indicators; dropdowns for organization, status,
  output type, availability (Desktop / Web / none). Filter state lives in the URL hash.
- Table, default sort by priority rank ascending (missing last, ties by name), any column
  sortable:
  `Priority | Workflow | Organization | Status | Desktop | Web | Outputs | Indicators | CI | Issues`
- Badges in the Workflow cell for `metadata_missing`, `spec_missing`, `visibility: private`,
  `archived`, and `errors`. Status and CI colour-coded.
- Row click expands a drill-down (one open at a time; open id in the URL hash): description,
  maintainers, each deliverable with its components (type, description, indicators), last CI
  run link, "Edit in registry" link, notes, and the open issues list (number, title, labels,
  age, assignee) each linking to GitHub.

**Outputs tab**
- One row per component across the fleet:
  `Workflow | Deliverable | Deliverable type | Component | Component type | Description | Indicators`
- Filters: indicator, component type, deliverable type, organization; text search over
  component name and description. Clicking the workflow cell jumps to its drill-down.

**Unregistered panel**: collapsed section at the bottom listing `unregistered` repos with a
link to each and to `registry.yaml`.

**Error states**: failed `data.json` load shows a message, not an empty table.

## Testing

- `monitor/tests/test_collect.py` — flat pytest functions; GitHub client replaced by a fake
  keyed on URL. Cases: registry validation (bad status, duplicate id, missing repo); flat and
  nested outputs normalise identically; private repo → null availability even when in the
  catalog; missing `ecoscope-web` branch → null web version; unknown indicator flagged;
  alias mapping; 404 on one repo isolates to that record; issues exclude pull requests;
  priority sort order helper.
- `monitor/tests/test_discover.py` — root `spec.yaml` detection; three-group diff.
- One live smoke test, skipped without a token, running `collect.py --only wt-ndvi` and
  asserting metadata and a desktop version are present.
- `monitor/sample-data.json` committed for opening `index.html` locally.
- pytest runs in `monitor.yml` before deploy.

## Out of scope (for now)

In-page editing; private hosting; snapshot history; web availability read from
ecoscope-server; PR listings; migrating the other 22 repos' metadata (the flat/absent shapes
render with badges instead).
