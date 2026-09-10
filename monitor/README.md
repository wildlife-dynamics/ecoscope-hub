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

    cd monitor
    export MONITOR_PAT=$(gh auth token)      # needs read:project for epic fields
    mkdir -p build
    pixi run discover -- --json > build/unregistered.json
    pixi run collect -- --unregistered build/unregistered.json
    python -m http.server 8765               # then open http://localhost:8765/index.html

`index.html?data=sample-data.json` renders the committed fixture without a token.

## Tests

    cd monitor
    pixi run test                            # unit tests, no network when MONITOR_PAT/GITHUB_TOKEN are unset (the live test skips)
    MONITOR_PAT=$(gh auth token) pixi run test -- tests/test_live.py   # live smoke test

## One-time setup

The Action needs a repo secret `MONITOR_PAT`: a fine-grained personal access token for the
`wildlife-dynamics` org with **Organization permissions → Projects: read** and **Repository
permissions → Contents, Issues, Actions, Metadata: read** on all repos. Without it, epics show
errors and private repos do not resolve.

Two one-time commands, then a manual run:

    gh api -X POST repos/wildlife-dynamics/ecoscope-hub/pages -f build_type=workflow   # enable Pages with source = GitHub Actions
    gh secret set MONITOR_PAT --repo wildlife-dynamics/ecoscope-hub                     # set the secret above
    gh workflow run monitor.yml --repo wildlife-dynamics/ecoscope-hub                   # run the workflow once by hand

The first deploy fails until Pages is enabled.

## Visibility

The site is public. Registry entries for private repos publish their epic, sub-issue, and issue
titles at a public URL. Omit such an entry from the registry if that is not acceptable.

## Indicators

`indicators.yaml` is the canonical vocabulary. Add an id with a label and aliases when a spec
uses an indicator the monitor flags as unknown.
