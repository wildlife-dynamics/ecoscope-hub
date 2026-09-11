import os
import time

import requests

API = "https://api.github.com"


class GitHubError(Exception):
    pass


class NotFound(GitHubError):
    pass


class GitHubClient:
    def __init__(self, token=None, session=None):
        self.token = token or os.environ.get("MONITOR_PAT") or os.environ.get("GITHUB_TOKEN")
        self.session = session or requests.Session()

    def _headers(self, extra=None):
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if extra:
            headers.update(extra)
        return headers

    def _request(self, method, url, headers=None, **kwargs):
        response = None
        for _ in range(3):
            response = self.session.request(method, url, headers=self._headers(headers), timeout=30, **kwargs)
            limited = response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0"
            if not limited:
                return response
            reset = int(response.headers.get("X-RateLimit-Reset", "0"))
            time.sleep(max(1, min(reset - time.time(), 120)))
        return response

    def _check(self, response, what):
        if response.status_code == 404:
            raise NotFound(what)
        if response.status_code >= 400:
            raise GitHubError(f"{response.status_code} {what}: {response.text[:200]}")

    def get(self, path, params=None):
        response = self._request("GET", API + path, params=params)
        self._check(response, path)
        return response.json()

    def paginate(self, path, params=None):
        params = dict(params or {}, per_page=100)
        url, items = API + path, []
        while url:
            response = self._request("GET", url, params=params)
            self._check(response, path)
            items.extend(response.json())
            url = response.links.get("next", {}).get("url")
            params = None
        return items

    def get_text(self, repo, path, ref):
        response = self._request(
            "GET",
            f"{API}/repos/{repo}/contents/{path}",
            headers={"Accept": "application/vnd.github.raw+json"},
            params={"ref": ref},
        )
        self._check(response, f"{repo}:{path}@{ref}")
        return response.text

    def graphql(self, query, variables):
        response = self._request(
            "POST", API + "/graphql", headers={"GraphQL-Features": "issue_types"}, json={"query": query, "variables": variables}
        )
        self._check(response, "graphql")
        body = response.json()
        if body.get("errors"):
            raise GitHubError("; ".join(e.get("message", "?") for e in body["errors"]))
        return body["data"]
