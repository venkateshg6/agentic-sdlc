"""SQLite atomic checkpoints and hash-linked event journal."""
import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class StateDB:
    def __init__(self, path):
        self.path = path
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, state TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                    payload TEXT NOT NULL, previous TEXT NOT NULL, hash TEXT NOT NULL);
            ''')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def save(self, state, kind, detail):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            last = db.execute("SELECT hash FROM events WHERE run_id=? ORDER BY seq DESC LIMIT 1", (state["id"],)).fetchone()
            previous = last[0] if last else "0" * 64
            payload = canonical({"time": time.time(), "kind": kind, "revision": state["revision"], "detail": detail,
                                 "state_hash": digest(state)})
            hash_value = hashlib.sha256((previous + payload).encode()).hexdigest()
            db.execute("INSERT INTO events(run_id,payload,previous,hash) VALUES(?,?,?,?)",
                       (state["id"], payload, previous, hash_value))
            db.execute("INSERT INTO runs VALUES(?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state",
                       (state["id"], canonical(state)))

    def load(self, run_id):
        with self.db() as db:
            row = db.execute("SELECT state FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise ValueError("Unknown run")
        state = json.loads(row[0])
        events = self.events(run_id)
        if not self.verify(run_id) or events[-1]["state_hash"] != digest(state):
            raise ValueError("Audit/checkpoint integrity verification failed")
        return state

    def events(self, run_id):
        with self.db() as db:
            return [dict(json.loads(p), seq=n, previous=prev, hash=h) for n, p, prev, h in
                    db.execute("SELECT seq,payload,previous,hash FROM events WHERE run_id=? ORDER BY seq", (run_id,))]

    def verify(self, run_id):
        previous = "0" * 64
        with self.db() as db:
            for payload, prev, h in db.execute("SELECT payload,previous,hash FROM events WHERE run_id=? ORDER BY seq", (run_id,)):
                if prev != previous or hashlib.sha256((previous + payload).encode()).hexdigest() != h:
                    return False
                previous = h
        return True

    def all(self):
        with self.db() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT state FROM runs")]
