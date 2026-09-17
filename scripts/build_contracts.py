"""Generate version-controlled API and run contracts from explicit definitions."""
import json
from pathlib import Path


def build():
    ref = lambda name: {"$ref": "#/components/schemas/" + name}
    response = lambda description, schema: {"description": description, "content": {"application/json": {"schema": schema}}}
    error = response("Request rejected or service unavailable", ref("Error"))
    common = {str(code): error for code in (400, 401, 404, 405, 409, 410, 413, 415, 422, 429, 500, 503)}
    code = {"name": "code", "in": "path", "required": True, "schema": {"type": "string", "pattern": "^[A-Za-z0-9_-]{4,32}$"}}
    properties = {"code": {"type": "string"}, "url": {"type": "string", "format": "uri"},
                  "created_at": {"type": "number"}, "expires_at": {"type": ["number", "null"]},
                  "disabled": {"type": "integer", "enum": [0, 1]}, "clicks": {"type": "integer", "minimum": 0}}
    spec = {"openapi": "3.1.0", "info": {"title": "Governed URL Shortener", "version": "1.0.0"},
            "servers": [{"url": "http://127.0.0.1:8000"}], "security": [{"bearerAuth": []}],
            "paths": {
                "/health": {"get": {"operationId": "health", "security": [], "responses": {"200": response("Healthy", {"type": "object"})}}},
                "/api/v1/urls": {"post": {"operationId": "createUrl", "parameters": [{"name": "Idempotency-Key", "in": "header", "schema": {"type": "string", "maxLength": 128}}],
                    "requestBody": {"required": True, "content": {"application/json": {"schema": ref("CreateUrl")}}},
                    "responses": {**common, "201": response("Created or idempotently replayed", {"allOf": [ref("Url"), {"type": "object", "properties": {"short_path": {"type": "string"}}}]})}}},
                "/api/v1/urls/{code}": {"parameters": [code],
                    "get": {"operationId": "getUrl", "responses": {**common, "200": response("URL details", ref("Url"))}},
                    "delete": {"operationId": "disableUrl", "responses": {**common, "200": response("Disabled (soft delete)", {"type": "object", "properties": {"disabled": {"type": "boolean"}}})}}},
                "/api/v1/urls/{code}/analytics": {"parameters": [code], "get": {"operationId": "getAnalytics", "responses": {**common,
                    "200": response("Aggregate counts only; no visitor PII", {"type": "object", "properties": {"code": {"type": "string"}, "clicks": {"type": "integer"}, "daily": {"type": "array", "items": {"type": "object", "properties": {"day": {"type": "string"}, "clicks": {"type": "integer"}}}}}})}}},
                "/r/{code}": {"parameters": [code], "get": {"operationId": "redirectUrl", "security": [], "responses": {**common, "302": {"description": "Redirect and count one click", "headers": {"Location": {"schema": {"type": "string", "format": "uri"}}}}}}}},
            "components": {"securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}}, "schemas": {
                "CreateUrl": {"type": "object", "required": ["url"], "additionalProperties": False, "properties": {
                    "url": {"type": "string", "format": "uri", "maxLength": 2048},
                    "alias": {"type": "string", "pattern": "^[A-Za-z0-9_-]{4,32}$"},
                    "ttl_seconds": {"type": "integer", "minimum": 1, "maximum": 31536000}}},
                "Url": {"type": "object", "required": list(properties), "properties": properties},
                "Error": {"type": "object", "required": ["error", "request_id"], "properties": {"error": {"type": "string"}, "request_id": {"type": "string"}}}}}}
    Path("docs/openapi.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")


if __name__ == "__main__":
    build()
