from gh import GitHubError
from metadata import parse_epic_url

WD_PROJECT_NUMBER = 9
EPIC_TYPES = {"Workflow", "Epic"}
FIELD_KEYS = {"Status": "status", "Priority": "priority", "Size": "size", "Project": "project"}

QUERY = """
query($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    issue(number: $number) {
      title state url
      issueType { name }
      assignees(first: 10) { nodes { login } }
      subIssuesSummary { total completed }
      projectItems(first: 20) {
        nodes {
          project { number title url }
          fieldValues(first: 30) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field { ... on ProjectV2SingleSelectField { name } }
              }
              ... on ProjectV2ItemFieldTextValue {
                text
                field { ... on ProjectV2Field { name } }
              }
            }
          }
        }
      }
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


def fetch_epic(client, url):
    owner, name, number = parse_epic_url(url)
    after, issue, sub_issues = None, None, []
    while True:
        data = client.graphql(QUERY, {"owner": owner, "name": name, "number": number, "after": after})
        page = (data.get("repository") or {}).get("issue")
        if page is None:
            raise GitHubError(f"epic not found: {url}")
        issue = issue or page
        sub_issues.extend(_sub_issue(n) for n in page["subIssues"]["nodes"])
        info = page["subIssues"]["pageInfo"]
        if not info.get("hasNextPage"):
            break
        after = info["endCursor"]

    items = issue.get("projectItems", {}).get("nodes", [])
    fields = _pick_fields(items)
    issue_type = (issue.get("issueType") or {}).get("name")
    errors = []
    if issue_type not in EPIC_TYPES:
        errors.append(f"epic issue type is {issue_type!r}, expected Workflow or Epic")
    summary = issue.get("subIssuesSummary") or {}
    assignees = [n["login"] for n in issue.get("assignees", {}).get("nodes", []) if n.get("login")]
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
