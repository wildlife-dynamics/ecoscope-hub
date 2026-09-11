from conftest import FakeResponse
from epic import build_epic_record, continue_sub_issues
from gh import API


def issue_node(sub_nodes=(), has_next=False, project_items=None, issue_type="Workflow", assignees=None, number=1):
    return {
        "number": number,
        "title": "NDVI",
        "state": "OPEN",
        "url": "https://github.com/o/r/issues/1",
        "issueType": {"name": issue_type} if issue_type else None,
        "assignees": {"nodes": [{"login": a} for a in (assignees or [])]},
        "subIssuesSummary": {"total": 3, "completed": 1},
        "projectItems": {"nodes": project_items or []},
        "subIssues": {
            "pageInfo": {"hasNextPage": has_next, "endCursor": "c1" if has_next else None},
            "nodes": list(sub_nodes),
        },
    }


def project_item(number, title, project_text=None, **fields):
    nodes = [{"name": v, "field": {"name": k}} for k, v in fields.items()]
    if project_text is not None:
        nodes.append({"text": project_text, "field": {"name": "Project"}})
    nodes.append({})
    return {"project": {"number": number, "title": title, "url": f"https://github.com/orgs/o/projects/{number}"}, "fieldValues": {"nodes": nodes}}


def sub(number, state="OPEN", itype="Bug", repo="o/other"):
    return {"number": number, "title": f"s{number}", "state": state, "url": f"https://github.com/{repo}/issues/{number}", "issueType": {"name": itype}, "repository": {"nameWithOwner": repo}}


def test_build_epic_record_reads_fields_from_wd_project_first():
    items = [project_item(41, "Eden", Status="Done", Priority="P3"), project_item(9, "Wildlife Dynamics", Status="In progress", Priority="P1", Size="M", project_text="WD General")]
    issue = issue_node([sub(741)], project_items=items, assignees=["yun-wu", "octocat"])
    record, errors = build_epic_record(issue, "https://github.com/o/r/issues/1")
    assert errors == []
    assert record["status"] == "In progress"
    assert record["priority"] == "P1"
    assert record["size"] == "M"
    assert record["project"] == "WD General"
    assert record["type"] == "Workflow"
    assert record["assignees"] == ["yun-wu", "octocat"]
    assert record["sub_issues"] == [{"number": 741, "repo": "o/other", "title": "s741", "state": "OPEN", "type": "Bug", "url": "https://github.com/o/other/issues/741"}]
    assert record["sub_issues_total"] == 3
    assert record["sub_issues_completed"] == 1


def test_build_epic_record_falls_back_to_first_project_with_fields():
    items = [project_item(41, "Eden"), project_item(40, "KBoPT", Status="Ready", Priority="P2")]
    record, _ = build_epic_record(issue_node([], project_items=items), "https://github.com/o/r/issues/1")
    assert record["status"] == "Ready"
    assert record["priority"] == "P2"
    assert record["size"] is None


def test_continue_sub_issues_paginates(client, session):
    session.add("POST", f"{API}/graphql", FakeResponse(200, {"data": {"repository": {"issue": {
        "subIssues": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": [sub(2)]},
    }}}}))
    more = continue_sub_issues(client, "o", "r", 1, "c1")
    assert [s["number"] for s in more] == [2]
    assert session.calls[0]["json"]["variables"] == {"owner": "o", "name": "r", "number": 1, "after": "c1"}


def test_build_epic_record_flags_unexpected_type():
    record, errors = build_epic_record(issue_node([], issue_type="Bug"), "https://github.com/o/r/issues/1")
    assert record["type"] == "Bug"
    assert errors == ["epic issue type is 'Bug', expected Workflow or Epic"]


def test_build_epic_record_missing_type_is_flagged():
    record, errors = build_epic_record(issue_node([], issue_type=None), "https://github.com/o/r/issues/1")
    assert record["type"] is None
    assert errors == ["epic issue type is None, expected Workflow or Epic"]


def test_build_epic_record_project_text_field_absent_is_none():
    items = [project_item(9, "Wildlife Dynamics", Status="Ready")]
    record, _ = build_epic_record(issue_node([], project_items=items), "https://github.com/o/r/issues/1")
    assert record["project"] is None


def test_build_epic_record_no_assignees_is_empty_list():
    record, _ = build_epic_record(issue_node([]), "https://github.com/o/r/issues/1")
    assert record["assignees"] == []


def test_build_epic_record_url_falls_back_when_issue_has_none():
    issue = issue_node([])
    issue["url"] = None
    record, _ = build_epic_record(issue, "https://github.com/fallback")
    assert record["url"] == "https://github.com/fallback"
