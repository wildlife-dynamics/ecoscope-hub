import os

import pytest

from collect import collect_workflow, fetch_catalog
from gh import GitHubClient
from metadata import load_indicators

TOKEN = os.environ.get("MONITOR_PAT") or os.environ.get("GITHUB_TOKEN")

pytestmark = pytest.mark.skipif(not TOKEN, reason="needs MONITOR_PAT or GITHUB_TOKEN")


def test_live_ndvi_resolves_epic():
    client = GitHubClient()
    catalog = fetch_catalog(client.session)
    vocab = load_indicators(os.path.join(os.path.dirname(__file__), "..", "indicators.yaml"))
    entry = {"id": "ndvi", "repo": "wildlife-dynamics/ndvi"}
    record = collect_workflow(entry, client, catalog, vocab)
    assert record["errors"] == []
    assert record["epic"]["type"] == "Workflow"
