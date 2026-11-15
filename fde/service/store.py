"""The durable log: every note read, every escalation and every gate run, in a hash-chained audit trail.

In memory by default; on Postgres when DATABASE_URL is set. Entries are only ever appended, and the sequence number is
the primary key, so two writers racing for the same slot cannot fork the chain.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass
from typing import Any, Protocol

GENESIS = "0" * 64


@dataclass(frozen=True)
class Entry:
    seq: int
    at_week: int
    actor: str
    action: str
    subject: str
    detail: dict[str, Any]
    prev_hash: str
    hash: str


def digest(seq: int, at_week: int, actor: str, action: str, subject: str, detail: dict[str, Any], prev: str) -> str:
    body = json.dumps([seq, at_week, actor, action, subject, detail, prev], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(body.encode()).hexdigest()


class Log(Protocol):
    def last(self) -> Entry | None: ...

    def append(self, entry: Entry) -> bool: ...

    def all(self) -> list[Entry]: ...


class MemoryLog:
    def __init__(self) -> None:
        self._entries: list[Entry] = []
        self._lock = threading.Lock()

    def last(self) -> Entry | None:
        with self._lock:
            return self._entries[-1] if self._entries else None

    def append(self, entry: Entry) -> bool:
        with self._lock:
            expected = self._entries[-1].seq + 1 if self._entries else 1
            if entry.seq != expected:
                return False
            self._entries.append(entry)
            return True

    def all(self) -> list[Entry]:
        with self._lock:
            return list(self._entries)


class PostgresLog:
    SCHEMA = "create table if not exists audit (seq bigint primary key, entry jsonb not null)"

    def __init__(self, url: str) -> None:
        import psycopg

        self._psycopg = psycopg
        self._conn = psycopg.connect(url, autocommit=True)
        with self._conn.cursor() as cur:
            cur.execute(self.SCHEMA)

    def last(self) -> Entry | None:
        with self._conn.cursor() as cur:
            cur.execute("select entry from audit order by seq desc limit 1")
            row = cur.fetchone()
        return Entry(**row[0]) if row else None

    def append(self, entry: Entry) -> bool:
        try:
            with self._conn.cursor() as cur:
                cur.execute("insert into audit (seq, entry) values (%s, %s)",
                            (entry.seq, self._psycopg.types.json.Jsonb(asdict(entry))))
            return True
        except self._psycopg.errors.UniqueViolation:
            return False

    def all(self) -> list[Entry]:
        with self._conn.cursor() as cur:
            cur.execute("select entry from audit order by seq")
            return [Entry(**r[0]) for r in cur.fetchall()]


class Audit:
    def __init__(self, log: Log) -> None:
        self.log = log

    def record(self, at_week: int, actor: str, action: str, subject: str, detail: dict[str, Any]) -> Entry:
        for _ in range(100):
            last = self.log.last()
            seq = (last.seq + 1) if last else 1
            prev = last.hash if last else GENESIS
            entry = Entry(seq, at_week, actor, action, subject, detail, prev,
                          digest(seq, at_week, actor, action, subject, detail, prev))
            if self.log.append(entry):
                return entry
        raise RuntimeError("audit log contention")

    def verify(self) -> dict[str, Any]:
        prev = GENESIS
        entries = self.log.all()
        for n, e in enumerate(entries, start=1):
            ok = e.seq == n and e.prev_hash == prev and e.hash == digest(e.seq, e.at_week, e.actor, e.action,
                                                                         e.subject, e.detail, prev)
            if not ok:
                return {"intact": False, "entries": len(entries), "firstBrokenSeq": e.seq}
            prev = e.hash
        return {"intact": True, "entries": len(entries), "firstBrokenSeq": None}
