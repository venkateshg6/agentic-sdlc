"""Transactional URL storage; no network fetching of user-supplied URLs."""
import hashlib
import ipaddress
import json
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from shortener.policy import is_expired


class Problem(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


def validate_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise Problem(422, "URL must be a string of at most 2048 characters")
    if any(ord(c) <= 32 or ord(c) == 127 for c in value):
        raise Problem(422, "URL contains whitespace or control characters")
    try:
        parts = urlsplit(value)
        host = parts.hostname
        port = parts.port
    except ValueError:
        raise Problem(422, "Malformed URL") from None
    if parts.scheme not in {"http", "https"} or not host or parts.username or parts.password:
        raise Problem(422, "Public HTTP(S) URL without credentials required")
    if port is not None and not 1 <= port <= 65535:
        raise Problem(422, "Invalid port")
    if host.lower() == "localhost" or host.lower().endswith((".localhost", ".local", ".internal")):
        raise Problem(422, "Local destinations are not permitted")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if "." not in host or not re.fullmatch(r"[A-Za-z0-9.-]+", host):
            raise Problem(422, "Public ASCII hostname required") from None
    else:
        if not address.is_global:
            raise Problem(422, "Private/reserved address is not permitted")
    return value


class Store:
    def __init__(self, path, clock=time.time, code_factory=None):
        self.path = str(path)
        self.clock = clock
        self.code_factory = code_factory or (lambda: secrets.token_urlsafe(6))
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS urls (
                    code TEXT PRIMARY KEY, url TEXT NOT NULL,
                    created_at REAL NOT NULL, expires_at REAL,
                    disabled INTEGER NOT NULL DEFAULT 0 CHECK(disabled IN (0,1)),
                    clicks INTEGER NOT NULL DEFAULT 0 CHECK(clicks >= 0));
                CREATE TABLE IF NOT EXISTS idempotency (
                    key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
                    code TEXT NOT NULL REFERENCES urls(code));
                CREATE TABLE IF NOT EXISTS daily_clicks (
                    code TEXT NOT NULL REFERENCES urls(code), day TEXT NOT NULL,
                    clicks INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(code, day));
                CREATE TABLE IF NOT EXISTS rate_limits (
                    bucket TEXT PRIMARY KEY, started REAL NOT NULL, count INTEGER NOT NULL);
            ''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def limit(self, bucket, maximum=120, window=60):
        now = self.clock()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM rate_limits WHERE started < ?", (now - window,))
            row = db.execute("SELECT count FROM rate_limits WHERE bucket=?", (bucket,)).fetchone()
            if row and row[0] >= maximum:
                raise Problem(429, "Rate limit exceeded; retry after 60 seconds")
            db.execute("INSERT INTO rate_limits VALUES(?,?,1) ON CONFLICT(bucket) DO UPDATE SET count=count+1",
                       (bucket, now))

    def create(self, body, idem=None):
        if not isinstance(body, dict) or set(body) - {"url", "alias", "ttl_seconds"}:
            raise Problem(422, "Expected url, optional alias and ttl_seconds")
        url = validate_url(body.get("url"))
        alias, ttl = body.get("alias"), body.get("ttl_seconds")
        if alias is not None and (not isinstance(alias, str) or not re.fullmatch(r"[A-Za-z0-9_-]{4,32}", alias)):
            raise Problem(422, "Alias must contain 4-32 letters, digits, hyphens or underscores")
        if ttl is not None and (type(ttl) is not int or not 1 <= ttl <= 31536000):
            raise Problem(422, "ttl_seconds must be an integer between 1 and 31536000")
        if idem is not None and (not isinstance(idem, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", idem)):
            raise Problem(422, "Invalid Idempotency-Key")
        fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        now = self.clock()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if idem:
                old = db.execute("SELECT * FROM idempotency WHERE key=?", (idem,)).fetchone()
                if old:
                    if old["fingerprint"] != fingerprint:
                        raise Problem(409, "Idempotency key reused with different input")
                    return dict(db.execute("SELECT * FROM urls WHERE code=?", (old["code"],)).fetchone())
            for _ in range(5):
                code = alias or self.code_factory()
                try:
                    db.execute("INSERT INTO urls(code,url,created_at,expires_at) VALUES(?,?,?,?)",
                               (code, url, now, now + ttl if ttl else None))
                    break
                except sqlite3.IntegrityError:
                    if alias:
                        raise Problem(409, "Alias already exists") from None
            else:
                raise Problem(503, "Could not allocate code after five attempts")
            if idem:
                db.execute("INSERT INTO idempotency VALUES(?,?,?)", (idem, fingerprint, code))
            return dict(db.execute("SELECT * FROM urls WHERE code=?", (code,)).fetchone())

    def get(self, code):
        with self.connection() as db:
            row = db.execute("SELECT * FROM urls WHERE code=?", (code,)).fetchone()
            if not row:
                raise Problem(404, "Link not found")
            return dict(row)

    def redirect(self, code):
        now = self.clock()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM urls WHERE code=?", (code,)).fetchone()
            if not row:
                raise Problem(404, "Link not found")
            if row["disabled"] or is_expired(row["expires_at"], now):
                raise Problem(410, "Link expired or disabled")
            db.execute("UPDATE urls SET clicks=clicks+1 WHERE code=?", (code,))
            day = time.strftime("%Y-%m-%d", time.gmtime(now))
            db.execute("INSERT INTO daily_clicks VALUES(?,?,1) ON CONFLICT(code,day) DO UPDATE SET clicks=clicks+1",
                       (code, day))
            return row["url"]

    def disable(self, code):
        with self.connection() as db:
            if db.execute("UPDATE urls SET disabled=1 WHERE code=?", (code,)).rowcount == 0:
                raise Problem(404, "Link not found")

    def analytics(self, code):
        item = self.get(code)
        with self.connection() as db:
            days = [dict(r) for r in db.execute("SELECT day,clicks FROM daily_clicks WHERE code=? ORDER BY day", (code,))]
        return {"code": code, "clicks": item["clicks"], "daily": days}
