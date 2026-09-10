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


COMPONENT_TYPES = {"map", "plot", "table", "text", "figure"}


def load_indicators(path):
    data = yaml.safe_load(Path(path).read_text()) or {}
    vocab = {}
    for canonical, spec in (data.get("indicators") or {}).items():
        spec = spec or {}
        names = [canonical, spec.get("label") or canonical, *(spec.get("aliases") or [])]
        for name in names:
            vocab[str(name).strip().lower()] = canonical
    return vocab


def _indicator_name(item):
    if isinstance(item, dict):
        return str(item.get("name") or "").strip()
    return str(item or "").strip()


def normalize_indicators(raw, vocab):
    canonical, unknown = [], []
    for item in raw or []:
        name = _indicator_name(item)
        if not name:
            continue
        key = name.lower()
        if key in vocab:
            if vocab[key] not in canonical:
                canonical.append(vocab[key])
        elif name not in unknown:
            unknown.append(name)
    return canonical, unknown


def _component(entry, vocab):
    indicators, unknown = normalize_indicators(entry.get("indicators"), vocab)
    return (
        {
            "name": str(entry.get("name") or ""),
            "type": str(entry.get("type") or ""),
            "description": str(entry.get("description") or ""),
            "indicators": indicators,
        },
        unknown,
    )


def normalize_outputs(meta, fallback_name, vocab):
    raw = (meta or {}).get("outputs") or []
    outputs, all_indicators, all_unknown = [], [], []
    implicit = None

    def note(indicators, unknown):
        for i in indicators:
            if i not in all_indicators:
                all_indicators.append(i)
        for u in unknown:
            if u not in all_unknown:
                all_unknown.append(u)

    for entry in raw:
        if not isinstance(entry, dict):
            continue
        etype = str(entry.get("type") or "")
        if etype in COMPONENT_TYPES:
            component, unknown = _component(entry, vocab)
            note(component["indicators"], unknown)
            if implicit is None:
                implicit = {"name": f"{fallback_name} Dashboard", "type": "dashboard", "description": "", "components": []}
                outputs.append(implicit)
            implicit["components"].append(component)
            continue
        components = []
        for c in entry.get("components") or []:
            if isinstance(c, dict):
                component, unknown = _component(c, vocab)
                note(component["indicators"], unknown)
                components.append(component)
        top_indicators, unknown = normalize_indicators(entry.get("indicators"), vocab)
        note(top_indicators, unknown)
        output = {
            "name": str(entry.get("name") or ""),
            "type": etype,
            "description": str(entry.get("description") or ""),
            "components": components,
        }
        if etype == "dashboard" and implicit is None:
            implicit = output
        outputs.append(output)
    return outputs, all_indicators, all_unknown


def parse_version(text):
    try:
        data = yaml.safe_load(text or "")
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    try:
        return f"{int(data['MAJ'])}.{int(data['MIN'])}.{int(data['PATCH'])}"
    except (KeyError, TypeError, ValueError):
        return None
