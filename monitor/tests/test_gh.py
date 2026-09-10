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
