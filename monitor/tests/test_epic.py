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
