import json

import pytest

from gh import GitHubClient


class FakeResponse:
    def __init__(self, status=200, body=None, text=None, headers=None, links=None):
        self.status_code = status
        self._body = body
        self.text = text if text is not None else json.dumps(body)
        self.headers = headers or {}
        self.links = links or {}

    def json(self):
        return self._body


class FakeSession:
    def __init__(self):
        self.routes = {}
        self.calls = []

    def add(self, method, url, response):
        key = (method, url)
        if key in self.routes and len(self.routes[key]) == 1:
            self.routes[key].pop(0)
        self.routes.setdefault(key, []).append(response)

    def request(self, method, url, headers=None, timeout=None, params=None, json=None):
        self.calls.append({"method": method, "url": url, "params": params, "json": json, "headers": headers})
        queue = self.routes.get((method, url))
        if not queue:
            return FakeResponse(404, {"message": "Not Found"})
        item = queue.pop(0)
        if not queue:
            queue.append(item)
        return item(params, json) if callable(item) else item


@pytest.fixture
def session():
    return FakeSession()


@pytest.fixture
def client(session):
    return GitHubClient(token="t", session=session)
