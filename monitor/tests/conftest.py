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
        self._index = {}
        self._queue_len = {}

    def add(self, method, url, response):
        self.routes.setdefault((method, url), []).append(response)

    def request(self, method, url, headers=None, timeout=None, params=None, json=None):
        self.calls.append({"method": method, "url": url, "params": params, "json": json, "headers": headers})
        key = (method, url)
        queue = self.routes.get(key)
        if not queue:
            return FakeResponse(404, {"message": "Not Found"})
        i = self._index.get(key, 0)
        old_len = self._queue_len.get(key, 0)
        if len(queue) > old_len and i == old_len - 1 and i < len(queue) - 1:
            i = old_len
            self._index[key] = i
        item = queue[i]
        if i < len(queue) - 1:
            self._index[key] = i + 1
        self._queue_len[key] = len(queue)
        return item(params, json) if callable(item) else item


@pytest.fixture
def session():
    return FakeSession()


@pytest.fixture
def client(session):
    return GitHubClient(token="t", session=session)
