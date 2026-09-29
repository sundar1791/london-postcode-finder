import copy
import json
from types import SimpleNamespace


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, db: "FakeSupabase", table: str):
        self._db = db
        self._table = table
        self._op = "select"
        self._payload = None
        self._filters = []
        self._order = None
        self._limit = None

    def select(self, *_args, **_kwargs):
        self._op = "select"
        return self

    def insert(self, payload):
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def upsert(self, payload, **_kwargs):
        self._op = "upsert"
        self._payload = payload
        return self

    def eq(self, col, val):
        self._filters.append(lambda r: r.get(col) == val)
        return self

    def gt(self, col, val):
        self._filters.append(lambda r: r.get(col) is not None and r.get(col) > val)
        return self

    def gte(self, col, val):
        self._filters.append(lambda r: r.get(col) is not None and r.get(col) >= val)
        return self

    def order(self, col, desc=False):
        self._order = (col, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        rows = self._db.tables.setdefault(self._table, [])
        if self._op == "insert":
            new = self._payload if isinstance(self._payload, list) else [self._payload]
            rows.extend(copy.deepcopy(new))
            return _Result(new)
        matched = [r for r in rows if all(f(r) for f in self._filters)]
        if self._op == "update":
            for r in matched:
                r.update(self._payload)
            return _Result(matched)
        if self._op == "upsert":
            rows.append(copy.deepcopy(self._payload))
            return _Result([self._payload])
        if self._order:
            col, desc = self._order
            matched = sorted(matched, key=lambda r: r.get(col) or "", reverse=desc)
        if self._limit is not None:
            matched = matched[: self._limit]
        return _Result(copy.deepcopy(matched))


class FakeSupabase:
    def __init__(self, tables=None):
        self.tables = tables or {}

    def table(self, name):
        return _Query(self, name)


class FakeAnthropic:
    """Mimics anthropic.Anthropic().messages.create, returning a thinking block
    followed by a text block (the shape claude-sonnet-5 produces)."""

    def __init__(self, text=None, payload=None, raises=None):
        self.calls = []
        self._text = text if text is not None else json.dumps(payload or {})
        self._raises = raises
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises:
            raise self._raises
        return SimpleNamespace(stop_reason="end_turn", content=[
            SimpleNamespace(type="thinking", thinking="..."),
            SimpleNamespace(type="text", text=self._text),
        ])
