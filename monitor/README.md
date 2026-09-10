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
