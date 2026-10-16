"""Local family references and bounded usage, independent of document contents."""

import json
import time

LIMIT = 12
WINDOW_DAYS = 30


def reference(identity, scope=""):
    return json.dumps(
        [scope if identity.startswith("document/") else "", identity],
        ensure_ascii=False,
        separators=(",", ":"),
    )


class History:
    def __init__(self, source="", *, now=None):
        self.now = int(time.time() if now is None else now)
        try:
            data = json.loads(source)
        except (ValueError, TypeError):
            data = {}
        if not isinstance(data, dict) or data.get("version") != 1:
            data = {}
        self.entries = {}
        entries = data.get("entries", {})
        for key, value in entries.items() if isinstance(entries, dict) else ():
            if not isinstance(value, dict):
                continue
            identity, scope = value.get("identity"), value.get("scope", "")
            if not isinstance(identity, str) or not isinstance(scope, str):
                continue
            if key != reference(identity, scope):
                continue
            days = value.get("days", {})
            self.entries[key] = {
                "identity": identity,
                "scope": scope,
                "title": (
                    value.get("title")
                    if isinstance(value.get("title"), str)
                    else identity
                ),
                "last": value.get("last") if type(value.get("last")) is int else 0,
                "days": {
                    day: count
                    for day, count in (days.items() if isinstance(days, dict) else ())
                    if day.isdecimal()
                    and len(day) < 10
                    and 0 <= self.now // 86400 - int(day) < WINDOW_DAYS
                    and type(count) is int
                    and count > 0
                },
            }
        for name in ("favorites", "recent"):
            items = data.get(name, [])
            setattr(
                self,
                name,
                list(
                    dict.fromkeys(
                        key
                        for key in (items if isinstance(items, list) else [])
                        if isinstance(key, str) and key in self.entries
                    )
                ),
            )
        self.recent = self.recent[:LIMIT]
        self.prune()

    def prune(self):
        retained = set(self.favorites) | set(self.recent)
        self.entries = {
            key: value
            for key, value in self.entries.items()
            if key in retained or value["days"]
        }

    def entry(self, identity, scope, title):
        key = reference(identity, scope)
        value = self.entries.setdefault(
            key,
            {
                "identity": identity,
                "scope": scope if identity.startswith("document/") else "",
                "title": title,
                "last": 0,
                "days": {},
            },
        )
        value["title"] = title
        return key, value

    def use(self, identity, scope="", title=""):
        key, value = self.entry(identity, scope, title or identity)
        day = str(self.now // 86400)
        value["days"][day] = value["days"].get(day, 0) + 1
        value["last"] = self.now
        self.recent = [key, *(k for k in self.recent if k != key)][:LIMIT]

    def favorite(self, identity, scope="", title=""):
        key, _ = self.entry(identity, scope, title or identity)
        if key in self.favorites:
            self.favorites.remove(key)
        else:
            self.favorites.append(key)

    def move(self, key, offset):
        index = self.favorites.index(key)
        target = max(0, min(len(self.favorites) - 1, index + offset))
        self.favorites.insert(target, self.favorites.pop(index))

    def frequent(self):
        return sorted(
            (key for key, value in self.entries.items() if value["days"]),
            key=lambda key: (
                -sum(self.entries[key]["days"].values()),
                -self.entries[key]["last"],
                key,
            ),
        )[:LIMIT]

    def clear_recent(self):
        self.recent.clear()

    def reset_usage(self):
        self.recent.clear()
        for value in self.entries.values():
            value["days"].clear()
            value["last"] = 0

    def dumps(self):
        self.prune()
        return json.dumps(
            {
                "version": 1,
                "entries": self.entries,
                "favorites": self.favorites,
                "recent": self.recent,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
