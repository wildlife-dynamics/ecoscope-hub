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
