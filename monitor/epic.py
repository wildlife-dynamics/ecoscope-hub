WD_PROJECT_NUMBER = 9
EPIC_TYPES = {"Workflow", "Epic"}
FIELD_KEYS = {"Status": "status", "Priority": "priority", "Size": "size", "Project": "project"}

# Continuation query for repos whose latest epic has more than 100 sub-issues (rare).
# The first page comes from collect.py's REPO_QUERY, keyed on the same issue number.
SUB_ISSUES_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    issue(number: $number) {
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
        value = node.get("text") if node.get("text") is not None else node.get("name")
        if field_name in FIELD_KEYS and value is not None:
            fields[FIELD_KEYS[field_name]] = value
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


def build_epic_record(issue, url):
    """Build (record, errors) from a GraphQL issue node — the shape returned by
    collect.py's REPO_QUERY `epics.nodes[0]`. `issue["subIssues"]["nodes"]` holds
    at most the first page; pass its pageInfo to continue_sub_issues() for more.
    """
    items = issue.get("projectItems", {}).get("nodes", [])
    fields = _pick_fields(items)
    issue_type = (issue.get("issueType") or {}).get("name")
    errors = []
    if issue_type not in EPIC_TYPES:
        errors.append(f"epic issue type is {issue_type!r}, expected Workflow or Epic")
    summary = issue.get("subIssuesSummary") or {}
    assignees = [n["login"] for n in issue.get("assignees", {}).get("nodes", []) if n.get("login")]
    sub_issues = [_sub_issue(n) for n in issue.get("subIssues", {}).get("nodes", [])]
    record = {
        "url": issue.get("url") or url,
        "title": issue.get("title"),
        "state": issue.get("state"),
        "type": issue_type,
        "status": fields.get("status"),
        "priority": fields.get("priority"),
        "size": fields.get("size"),
        "project": fields.get("project"),
        "assignees": assignees,
        "sub_issues": sub_issues,
        "sub_issues_total": summary.get("total", len(sub_issues)),
        "sub_issues_completed": summary.get("completed", 0),
    }
    return record, errors


def continue_sub_issues(client, owner, name, number, after):
    """Fetch sub-issue pages beyond the first 100 (rare)."""
    sub_issues = []
    while True:
        data = client.graphql(SUB_ISSUES_QUERY, {"owner": owner, "name": name, "number": number, "after": after})
        page = (data.get("repository") or {}).get("issue")
        if page is None:
            break
        sub_issues.extend(_sub_issue(n) for n in page["subIssues"]["nodes"])
        info = page["subIssues"]["pageInfo"]
        if not info.get("hasNextPage"):
            break
        after = info["endCursor"]
    return sub_issues
