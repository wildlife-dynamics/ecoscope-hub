# Ecoscope Workflow Monitor — design

Date: 2026-09-10
Status: approved in conversation, awaiting written review

## Purpose

A single page where the internal team can see every ecoscope workflow the org maintains,
which partner project it is for (the board's Project field), where it is in its development lifecycle, whether and at
which version it is available on Ecoscope Desktop and the web platform, what it produces
(outputs and their indicators), whether CI is green, and which GitHub issues are
open. It must answer fleet-wide questions such as "which workflows calculate NDVI" and "is
there a map of last-visited patrol areas", and present workflows in priority order.

Audience: the internal team. Delivery: a public GitHub Pages site built on a schedule by a
GitHub Actions workflow in `ecoscope-hub`. The org is on the GitHub **Team** plan, so Pages
cannot be private; this was accepted explicitly. A later hosted version (Cloud Run + IAP with
in-page editing) reuses the collector and page unchanged; it is out of scope here.

## Sources of truth (hybrid model)

| Field group | Owner | Where |
|---|---|---|
| Which workflows exist | ecoscope-hub | `monitor/registry.yaml` (`id` + `repo` only) |
| Which issue is the epic | derived | the repo's most-recently-created issue of type `Workflow`, via GraphQL |
| Lifecycle status, priority, size, the board's `Project` text field, tracked sub-issues | GitHub Projects | the epic issue's project items (Wildlife Dynamics project #9 first) and sub-issues, via GraphQL |
| Name, description, maintainers, outputs → indicators | each workflow repo | `metadata:` block in `spec.yaml` on the default branch, falling back to `ecoscope-web` when the default branch has no `metadata:` block; `metadata_source` records which |
| Canonical indicator vocabulary | ecoscope-hub | `monitor/indicators.yaml` |
| Desktop availability + version | derived | repo is public; version from `VERSION.yaml` on `main`, at the path from the Desktop catalog JSON when the repo is listed there (catalog URLs resolved to each repo's canonical name so renames still match), else inferred from the repo tree — catalog membership does not gate whether a version is shown |
| Web availability + version | derived | repo is public **and** has an `ecoscope-web` branch; version from `VERSION.yaml` on that branch |
| Repo visibility (private repos are excluded), CI status, repo open issues | derived | GitHub API on every build |

Rule: **private repos are excluded from discovery and the snapshot**. Visibility is read from
the API on every build.

Nothing collected is stored in git. The snapshot lives only in the deployed Pages artifact and
is regenerated from scratch each run. (A `monitor-data` branch for history is a possible
later addition, not built now.)

## Registry — `monitor/registry.yaml`

```yaml
workflows:
  - id: ndvi                     # unique key; display name fallback when metadata is absent
    repo: wildlife-dynamics/ndvi  # required
```

That's it — no `epic:` field. The epic is resolved dynamically (see below) as the repo's own
most-recently-created issue of type "Workflow"; there is nothing to keep in sync here when an
epic is filed, closed, or replaced.

Validation (build fails on violation): duplicate `id`, `repo` missing, the same `repo` used by
more than one entry — each repo backs at most one workflow, since "the repo's latest
Workflow-typed issue" can't disambiguate two ids sharing a repo the way an explicit per-id
epic URL once could.

Editing: the page links each row to its epic (edit status/priority there) and to
`registry.yaml` in GitHub's web editor (add or retire a workflow). Committing there triggers a
rebuild. No in-page writes.

## Epic — what is read from it, and how it's found

**Resolution**: no registry field points at the epic. Instead, `collect.py` asks GitHub for
the repo's issues filtered to `type: Workflow`, ordered by creation date descending, and takes
the first (`issues(first: 1, filterBy: {type: "Workflow"}, orderBy: {field: CREATED_AT,
direction: DESC})`, part of the same combined query described in the Collector section below).
Open or closed doesn't matter — only the type and recency. A repo with no such issue simply
has no epic (`epic: null`); nothing is treated as an error.

**Fields read** from that issue:

- `title`, `state`, `url`, `issueType.name`. Accepted types: `Workflow` and `Epic`; any other
  type is recorded as an error on the record but the fields are still used.
- `projectItems`: for each project the epic is in, the project title, number, and URL, and its
  single-select field values. `status`, `priority`, `size` come from the **Wildlife Dynamics**
  project (#9) item when present, else from the first project item that has those fields.
  Vocabulary is whatever the Project defines today: Status `Backlog | Ready | In progress |
  In review | Done`; Priority `P0..P3`; Size `XS..XL`. The collector copies values verbatim
  and does not validate them.
- `project`: the board's free-text `Project` field (e.g. `WD General`, `Mara Triangle`), read
  like status/priority/size.
- `assignees`: the epic issue's own assignee logins (up to 10), shown as an Assignee column on
  the Workflows tab and in the modal's Epic block.
- `subIssues` (first 100, paginated further only if needed): number, title, state, url, repo,
  issue type; plus `subIssuesSummary` (`total`, `completed`). Sub-issues may live in any repo.

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

Outputs are shown exactly as declared: a flat list of `{name, type, description, indicators}`,
one entry per item in `metadata.outputs`, in declared order. No implicit grouping or
dashboard-wrapping.

```yaml
metadata:
  name: NDVI Workflow
  description: ...
  maintainers:
    - {name: ..., email: ..., role: owner}
  outputs:
    - name: NDVI Dashboard
      type: dashboard
      description: ...
    - name: NDVI Map
      type: map
      description: Mean NDVI per region of interest for the selected period
      indicators: [ndvi]
```

Compatibility: an entry may still carry a nested `components` list (the older shape); each
component is flattened into its own output entry, placed immediately after its parent, with
its own name/type/description/indicators — never nested in the output. `indicators` entries
may be strings or `{name: ...}` objects.

Repos with no `metadata:` block get `metadata_missing: true`; repos with no root `spec.yaml`
get `spec_missing: true`. Both still produce a row.

## Snapshot — `data.json`

```json
{
  "generated_at": "2026-09-10T12:00:00Z",
  "unregistered": [{"repo": "wildlife-dynamics/foo", "has_workflow_issue": false, "has_metadata": false}],
  "workflows": [
    {
      "id": "ndvi", "repo": "wildlife-dynamics/ndvi",
      "epic": {"url": "https://github.com/wildlife-dynamics/ndvi/issues/1",
               "title": "NDVI Workflow", "state": "OPEN", "type": "Workflow",
               "status": "In progress", "priority": "P1", "size": "M",
               "project": "WD General",
               "assignees": ["octocat"],
               "sub_issues": [{"number": 741, "repo": "wildlife-dynamics/ecoscope",
                               "title": "...", "state": "OPEN", "type": "Bug", "url": "..."}],
               "sub_issues_total": 2, "sub_issues_completed": 0},
      "archived": false,
      "name": "NDVI Workflow", "description": "...", "maintainers": [],
      "outputs": [{"name": "...", "type": "dashboard", "description": "...", "indicators": []},
                  {"name": "...", "type": "map", "description": "...", "indicators": ["ndvi"]}],
      "indicators": ["ndvi"], "unknown_indicators": [],
      "metadata_missing": false, "spec_missing": false,
      "task_libraries": [{"name": "ecoscope-platform", "version": ">=2.11.6, <2.12.0",
                          "channel": "https://repo.prefix.dev/ecoscope-workflows/"}],
      "wt_compiler_version": ">=0.5.2, <0.6.0",
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

`indicators` is the de-duplicated union over all outputs, for filtering. `epic` is `null`
when the registry entry has no epic or it could not be read.

## Collector — `monitor/collect.py`

Single file; dependencies `requests` and `pyyaml` from the hub pixi env. Per registry entry,
in order, each step recording an error string and continuing on failure:

0. Entries without `repo` stop here (empty record, no API calls at all).
1. **One combined GraphQL query** (`REPO_QUERY`, header `GraphQL-Features: issue_types`) —
   the single most important optimization in this file. Rather than one REST call apiece for
   repo info, `spec.yaml`, `pixi.toml`, the `ecoscope-web` branch check, and a separate epic
   lookup (5+ round trips), one query returns all of it together:
   - `isPrivate`, `isArchived`, `defaultBranchRef.name`.
   - `spec`/`pixi`: `object(expression: "HEAD:spec.yaml" | "HEAD:pixi.toml") { ... on Blob {
     text } }` — `null` when the file doesn't exist, no separate existence check needed.
   - `webBranch`: `ref(qualifiedName: "refs/heads/ecoscope-web")` — `null` when absent, no
     separate branch-exists call needed.
   - `webSpec`: the same `object(expression:)` trick against
     `refs/heads/ecoscope-web:spec.yaml`, fetched unconditionally alongside everything else
     (cheap — one more field on the same query) so the metadata fallback (step 2) needs no
     second round trip either.
   - `epics`: `issues(first: 1, filterBy: {type: "Workflow"}, orderBy: {field: CREATED_AT,
     direction: DESC})` with the project fields, assignees, and first 100 sub-issues nested
     inside — this is the dynamic epic resolution described above, folded into the same call.
   A repo the token can't resolve (private, deleted, or renamed away) surfaces as a GraphQL
   `errors` entry (`Could not resolve to a Repository...`) rather than an HTTP 404; either way
   it's recorded as one error and the rest of that record stays empty. A private repo that
   *does* resolve (`isPrivate: true`) is excluded from the snapshot entirely (return `None`,
   warn to stderr) — same behavior as before, just detected from this query instead of a
   separate REST call.
2. Parse the `spec` blob's `metadata:` block; normalise outputs and indicators. If it has no
   `metadata:` block and `webBranch` was non-null, parse the already-fetched `webSpec` blob
   instead. `metadata_source` records which one won (`main`/other default branch name,
   `ecoscope-web`, or `null` when neither has one). A YAML parse error on either blob is
   recorded as an error and treated the same as "no metadata" for that source.
3. `task_libraries` — the same `spec`/`webSpec` blob's top-level `requirements:` list (parsed
   once alongside step 2, no extra call), one `{name, version, channel}` entry per requirement.
4. `wt_compiler_version` — the `pixi` blob's `[dependencies].wt-compiler` pin (via stdlib
   `tomllib`); `null` when the file, table, or key is absent (a real gap for pre-`wt`-tooling
   repos, not an error).
5. Availability — still REST, since the two things left (a repo-tree walk and named-workflow
   CI runs) don't have as clean a GraphQL shape:
   - Fetch the Desktop catalog JSON once per run
     (`https://storage.googleapis.com/ecoscope-io-storage-public/ecoscope-desktop/hardcoded-template-catalog/workflow_templates.json`)
     and resolve each entry's `url` to its repo's canonical name. If the repo matches, read
     `VERSION.yaml` at its `version_file_path` on `main`. The catalog is a small, manually
     curated allowlist (a handful of entries) — most repos are not on it.
   - **`desktop_version` is not gated on catalog membership.** When the repo isn't in the
     catalog (or the catalog is unavailable), the path is inferred instead from the generated
     package dir (`<something>-workflow/VERSION.yaml`, discovered via `GET
     /repos/{repo}/git/trees/{ref}?recursive=1` on `main`) and read the same way — every
     public workflow with a compiled package gets a `desktop_version` regardless of whether
     Desktop's catalog has picked it up yet. A missing tree or file is not an error; only an
     unexpected failure while reading it is.
   - If `webBranch` was non-null, read `VERSION.yaml` at the same path (catalog or inferred)
     on `ecoscope-web`; if there is no path yet, infer one from that branch's tree directly.
6. Latest `test.yml` run on the default branch (REST — Actions data has no equivalent GraphQL
   shape) → `conclusion`, `html_url`; if the repo has no `test.yml` workflow, fall back to
   `ci.yml` the same way; null if neither exists.
7. Open issues in the repo (REST, `state=open`, excluding items with `pull_request` and items
   whose issue type is `Workflow` — the epic itself, when it lives in the same repo) → number,
   title, url, labels, created_at, assignee login.

One HTTP helper handles the token, pagination, and a bounded retry on 403 rate-limit
responses. Roughly 4-6 calls per repo now (down from ~8-11 before the query consolidation):
one `REPO_QUERY`, plus REST for the version tree-walk(s), CI, and issues — well under the
limits for a PAT, and importantly avoids the GitHub Search API (30 req/min) entirely; only
`discover.py` uses Search, and only for the handful of *unregistered* repos each run.

`--registry`, `--out`, `--only <id>` flags for local runs. Exit non-zero only on invalid
registry or an uncaught exception.

## Discovery — `monitor/discover.py`

1. List all non-archived, public repos across the configured GitHub owners — by default
   `wildlife-dynamics` and `ecoscope-platform-workflows-releases` (paginated per owner,
   `--org` repeatable to override); private repos are excluded.
2. A repo is a workflow repo iff it has `spec.yaml` at its root.
3. Compare with the registry and report three groups: workflow repos missing from the
   registry, registry entries whose repo is gone or archived, org repos without `spec.yaml`.
4. `--add` appends missing workflow repos to `registry.yaml` as stubs with `id` and `repo`
   and `epic` left empty (the page badges entries without an epic). Default is report-only.
5. Each missing repo is enriched with `has_workflow_issue` (GitHub search,
   `repo:<repo> type:Workflow`, `total_count > 0` — an epic already exists even though the repo
   isn't registered yet) and `has_metadata` (`spec.yaml`'s `metadata:` block is present). Both
   default to `false` on any read failure (warned, not fatal).
6. `--json` prints the missing group (with those two extra fields) for the collector, which
   embeds it as `unregistered`; the page shows both as badges next to the repo link.

## Action — `.github/workflows/monitor.yml`

Triggers: cron every hour; push to `main` touching `monitor/**` or the workflow file;
`pull_request` touching the same paths (any base branch); `workflow_dispatch`
(human-triggerable from the Actions UI or `gh workflow run monitor.yml`). The `deploy` job is
skipped (`if: github.event_name != 'pull_request'`) on PR runs — a PR only exercises `build`
(tests + discover + collect), it never publishes to Pages.

Steps: checkout → setup-pixi → `pytest monitor/tests` → `discover.py --json` →
`collect.py --out build/data.json` → copy `monitor/index.html` to `build/` →
`actions/upload-pages-artifact` → `actions/deploy-pages`.

Token: the default `GITHUB_TOKEN` cannot read org Projects, so a repo secret `MONITOR_PAT`
(fine-grained; org **Projects: read**, plus read on contents, issues, actions, metadata) is
required. Without it the job still runs but every epic records an error and the page shows
no status/priority; private repos also fail to resolve. Tests failing or the collector
crashing prevents deploy; the previous site stays up.

## Page — `monitor/index.html`

One file, inline CSS/JS, no dependencies, fetches `data.json` on load. Title "Ecoscope
Workflow Monitor". Light/dark via `prefers-color-scheme`. Works at phone width; tables scroll
horizontally inside their container.

**Header**: title; "generated N minutes ago" (amber when older than 12 h); links to the
Actions page (rebuild), to the Wildlife Dynamics project, and to `registry.yaml` in GitHub's
editor.

**Summary**: a two-row figures area above the tabs, computed over the whole fleet regardless
of active filters, laid out as a 6-column grid. Row one is six equal-width stat tiles: total
workflow templates, unique output names, on Desktop, on Web, and In progress / In review (the
last two count epics by board Status). Row two holds two charts, each spanning three columns
so the row totals the same width as row one: a workflows-by-Project donut (legend, per-slice
tooltips, smallest slices folded into "Other" past 7 distinct projects) and an "Open Workflows
by Priority" bar chart (`P0`..`P3` plus "No priority", bars coloured to match the table's
priority chips) that excludes workflows with no epic status and workflows whose epic status is
`Done` — it counts only work that is both tracked and still outstanding.

**Tabs**: Workflows, Outputs.

**Workflows tab**
- Filter bar: text search over id, name, indicators, description, repo, project, epic
  assignees, output names, and maintainer name/email; dropdowns for project, status, assignee
  (the epic's assignee logins), priority, output type, availability (Desktop / Web / none).
  Filter state lives in the URL hash.
- Table, default sort by priority (P0 first, missing last), then status in project order,
  then name; any column sortable:
  `Priority | Workflow | Project | Status | Assignee | Desktop | Web | Outputs | CI | Open work`
  `Open work` is open sub-issues + repo open issues; the `Outputs` cell lists each output's
  name as a chip, in declared order (title = type). The epic link itself moved into the
  drill-down modal.
- Badges in the Workflow cell for `metadata_missing`, `spec_missing`, `archived`, no epic,
  `unknown_indicators`, and `errors`. Status, priority, and CI colour-coded.
- Row click opens a modal (open id in the URL hash): repo link, last CI run link, "Edit in
  registry" link; description (with its `metadata_source` when set); maintainers; a **Status
  Tracking** block linking to the epic with its state, size, and assignees (no issue type or
  sub-issue count); the output list (name, type, description, indicator chips); **Repo
  issues** (the repo's open issues, excluding epics, with
  number, title, labels, age, assignee, each linking to GitHub); last, a **Build** block
  (`wt_compiler_version` and the `task_libraries` list — name and version only, no channel).
  There is no separate "Tracked work" list of
  the epic's sub-issues in the modal — `sub_issues_completed`/`sub_issues_total` in the Epic
  block is the only place that data still surfaces on the page.

**Outputs tab**
- One row per output across the fleet: `Workflow | Output | Type | Description | Indicators`
- Filters: indicator, type; text search over output name and description. No project filter
  here (the Workflows tab's project filter already covers it). Clicking the workflow cell
  opens its modal.

**Unregistered panel**: collapsed section at the bottom listing `unregistered` repos with a
link to each, a badge when `has_workflow_issue` is true ("has Workflow issue") and when
`has_metadata` is true ("has metadata"), and a link to `registry.yaml`.

**Error states**: failed `data.json` load shows a message, not an empty table.

## Testing

- `monitor/tests/test_epic.py` — pure unit tests for `build_epic_record` (given a GraphQL
  issue node, not a fetch) and `continue_sub_issues` (pagination continuation, GitHub client
  replaced by a fake): status/priority/size/project from project #9 preferred over another
  project, sub-issue pagination, non-`Workflow` type recorded as error, missing `Project` text
  field yields null, no assignees yields `[]`, a missing `url` on the issue falls back to the
  caller-supplied one.
- `monitor/tests/test_collect.py` — flat pytest functions; GitHub client replaced by a fake
  keyed on URL, with a small builder (`repo_query_response`) for the combined `REPO_QUERY`
  GraphQL response shape (and `add_repo_query_multi` for tests needing distinct responses per
  repo, dispatched on the query's `owner`/`name` variables since all GraphQL calls share one
  URL). Cases: registry validation (duplicate id, missing repo, same repo used by two ids);
  epic resolution folded into the combined query (repo not found via a null `repository` vs.
  a GraphQL `errors` array, both isolated to one error string; a malformed epic node's build
  failure isolated from the rest of the record; sub-issue pagination continuing past the first
  page); flat and nested-components outputs flatten identically; private repo → excluded from
  the snapshot; desktop version falls back to a tree-discovered path when the repo is not in
  the catalog, and is null (not an error) when no `VERSION.yaml` exists anywhere; missing
  `ecoscope-web` branch/blob → null web version/metadata; unknown indicator flagged; alias
  mapping (registry `repo` vs. the query's resolved `nameWithOwner`); issues exclude pull
  requests and the epic's own `Workflow`-typed issue; `task_libraries` read from the same
  `spec`/`webSpec` blob's `requirements:`; `wt_compiler_version` read from the `pixi` blob's
  `[dependencies]`, null (not an error) when the blob or key is absent; CI status falls back
  from `test.yml` to `ci.yml` when the former doesn't exist, preferring `test.yml` when both
  do; priority/status sort order helper.
- `monitor/tests/test_discover.py` — root `spec.yaml` detection; three-group diff;
  `has_metadata` true/false on the `metadata:` block, false when `spec.yaml` is absent;
  `has_workflow_issue` true/false on the search API's `total_count`.
- One live smoke test, skipped without a token, running `collect.py --only ndvi` and
  asserting metadata and a desktop version are present.
- `monitor/sample-data.json` committed for opening `index.html` locally.
- pytest runs in `monitor.yml` before deploy.

## Out of scope (for now)

In-page editing; private hosting; snapshot history; web availability read from
ecoscope-server; PR listings; writing to Projects; migrating the other 22 repos' metadata
(the flat/absent shapes render with badges instead).
