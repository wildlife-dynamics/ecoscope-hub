import re
from pathlib import Path

import yaml

EPIC_URL_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/issues/(\d+)/?$")


class RegistryError(Exception):
    pass


def parse_epic_url(url):
    m = EPIC_URL_RE.match(url or "")
    if not m:
        raise RegistryError(f"epic is not a GitHub issue URL: {url!r}")
    return m.group(1), m.group(2), int(m.group(3))


def load_registry(path):
    data = yaml.safe_load(Path(path).read_text()) or {}
    raw = data.get("workflows")
    if not isinstance(raw, list):
        raise RegistryError("registry must have a top-level 'workflows' list")
    entries, seen = [], set()
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or not item.get("id"):
            raise RegistryError(f"entry {i} is missing an id")
        wid = str(item["id"])
        if wid in seen:
            raise RegistryError(f"duplicate id: {wid}")
        seen.add(wid)
        repo = item.get("repo") or None
        epic = item.get("epic") or None
        if not repo and not epic:
            raise RegistryError(f"{wid}: needs repo or epic")
        if epic:
            parse_epic_url(epic)
        entries.append({"id": wid, "repo": repo, "epic": epic})
    return entries
