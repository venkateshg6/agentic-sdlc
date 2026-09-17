"""Small WSGI adapter. Bind localhost for evaluation; use a production server for deployment."""
import argparse
import hmac
import json
import logging
import os
import re
import sqlite3
import uuid
from http import HTTPStatus
from wsgiref.simple_server import make_server, WSGIRequestHandler

from shortener.service import Problem, Store

LOG = logging.getLogger("shortener")


def create_app(db_path, api_key):
    if not api_key or len(api_key) < 16:
        raise ValueError("SHORTENER_API_KEY must have at least 16 characters")
    store = Store(db_path)

    def app(env, start_response):
        request_id = uuid.uuid4().hex
        method, path = env["REQUEST_METHOD"], env.get("PATH_INFO", "")
        status, payload, extra = 200, {}, []
        try:
            if path == "/health" and method == "GET":
                with store.connection() as db:
                    db.execute("SELECT 1")
                payload = {"status": "ok"}
            else:
                store.limit(env.get("REMOTE_ADDR", "unknown"))
                if path.startswith("/api/"):
                    token = env.get("HTTP_AUTHORIZATION", "").removeprefix("Bearer ")
                    if not hmac.compare_digest(token.encode(), api_key.encode()):
                        raise Problem(401, "Bearer token required")
                if path == "/api/v1/urls" and method == "POST":
                    if env.get("CONTENT_TYPE", "").split(";")[0] != "application/json":
                        raise Problem(415, "application/json required")
                    try:
                        length = int(env.get("CONTENT_LENGTH") or "0")
                    except ValueError:
                        raise Problem(400, "Invalid content length") from None
                    if not 0 < length <= 8192:
                        raise Problem(413, "Body must be 1-8192 bytes")
                    try:
                        body = json.loads(env["wsgi.input"].read(length))
                    except (ValueError, UnicodeError):
                        raise Problem(400, "Invalid JSON") from None
                    payload = store.create(body, env.get("HTTP_IDEMPOTENCY_KEY"))
                    payload["short_path"] = "/r/" + payload["code"]
                    status = 201
                elif match := re.fullmatch(r"/api/v1/urls/([A-Za-z0-9_-]{4,32})(/analytics)?", path):
                    code, analytics = match.groups()
                    if method == "GET":
                        payload = store.analytics(code) if analytics else store.get(code)
                    elif method == "DELETE" and not analytics:
                        store.disable(code)
                        payload = {"disabled": True}
                    else:
                        raise Problem(405, "Method not allowed")
                elif method == "GET" and (match := re.fullmatch(r"/r/([A-Za-z0-9_-]{4,32})", path)):
                    status, payload = 302, {"redirect": True}
                    extra.append(("Location", store.redirect(match[1])))
                else:
                    raise Problem(404, "Route not found")
        except Problem as exc:
            status, payload = exc.status, {"error": exc.message, "request_id": request_id}
        except sqlite3.Error:
            status, payload = 503, {"error": "Storage temporarily unavailable", "request_id": request_id}
        except Exception:
            LOG.error("unexpected_failure request_id=%s", request_id)
            status, payload = 500, {"error": "Internal error", "request_id": request_id}
        if status == 429:
            extra.append(("Retry-After", "60"))
        data = json.dumps(payload).encode()
        start_response(f"{status} {HTTPStatus(status).phrase}", [
            ("Content-Type", "application/json"), ("Content-Length", str(len(data))),
            ("X-Request-ID", request_id), ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"), *extra])
        LOG.info(json.dumps({"request_id": request_id, "method": method, "status": status}))
        return [data]

    return app


class PrivateRequestHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        pass  # Structured logs above omit raw URLs, tokens and addresses.


def main():
    from pathlib import Path
    if Path(".env").exists():
        for line in Path(".env").read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('\"').strip("'"))
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    application = create_app(os.getenv("SHORTENER_DB", ".runtime/shortener.db"),
                             os.getenv("SHORTENER_API_KEY", ""))
    print(f"Local URL service: http://127.0.0.1:{args.port}/health", flush=True)
    with make_server("127.0.0.1", args.port, application, handler_class=PrivateRequestHandler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
