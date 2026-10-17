import asyncio
import json
import os
from typing import Any, Dict, Optional, Tuple

# Ensure test environment is initialized before any app module imports
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("API_KEY", "test-secret-key-that-is-at-least-32-chars-long")


def perform_asgi_request(
    app: Any,
    method: str,
    path: str,
    headers: Optional[Dict[str, str]] = None,
    body: Optional[bytes] = None,
) -> Tuple[int, Dict[str, str], bytes]:
    """
    Lightweight, in-process ASGI test client using pure standard library.
    Allows testing FastAPI routes without third-party test runners or httpx.
    """
    headers = headers or {}
    body = body or b""

    # Convert headers to ASGI format (lowercase bytes tuples)
    asgi_headers = [
        (k.lower().encode("latin1"), v.encode("latin1")) for k, v in headers.items()
    ]

    response_headers: Dict[str, str] = {}
    response_body_chunks: list[bytes] = []
    status_code: int = 500

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method.upper(),
        "path": path,
        "raw_path": path.encode("latin1"),
        "query_string": b"",
        "headers": asgi_headers,
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 80),
        "app": app,
    }

    async def receive() -> Dict[str, Any]:
        return {
            "type": "http.request",
            "body": body,
            "more_body": False,
        }

    async def send(message: Dict[str, Any]) -> None:
        nonlocal status_code
        if message["type"] == "http.response.start":
            status_code = message["status"]
            for k, v in message.get("headers", []):
                response_headers[k.decode("latin1")] = v.decode("latin1")
        elif message["type"] == "http.response.body":
            response_body_chunks.append(message.get("body", b""))

    asyncio.run(app(scope, receive, send))
    full_body = b"".join(response_body_chunks)
    return status_code, response_headers, full_body


def asgi_json_request(
    app: Any,
    method: str,
    path: str,
    headers: Optional[Dict[str, str]] = None,
    json_data: Optional[Any] = None,
) -> Tuple[int, Any]:
    """
    Send an ASGI request with JSON payload and parse JSON response.
    """
    req_headers = dict(headers or {})
    req_body = b""
    if json_data is not None:
        req_headers["content-type"] = "application/json"
        req_body = json.dumps(json_data).encode("utf-8")

    status, resp_headers, body = perform_asgi_request(
        app=app,
        method=method,
        path=path,
        headers=req_headers,
        body=req_body,
    )

    try:
        parsed_body = json.loads(body.decode("utf-8")) if body else None
    except Exception:
        parsed_body = body.decode("utf-8")

    return status, parsed_body
