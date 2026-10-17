import re
import threading
import time
import uuid
from collections import OrderedDict
from typing import Callable, List

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.status import (
    HTTP_413_CONTENT_TOO_LARGE,
    HTTP_429_TOO_MANY_REQUESTS,
)
from starlette.types import Message, Receive, Scope, Send

from app.core import config
from app.core.metrics import record_error, record_request
from app.core.security import get_client_ip

CORRELATION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Ensures every request has a validated correlation ID for tracing.
    Validates incoming X-Request-ID against a strict alphanumeric allowlist.
    Discards invalid or oversized values and generates a fresh UUID4.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        raw_id = request.headers.get("X-Request-ID")
        if raw_id and CORRELATION_ID_PATTERN.match(raw_id):
            request_id = raw_id
        else:
            request_id = str(uuid.uuid4())

        request.state.request_id = request_id
        record_request()

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        if response.status_code >= 400:
            record_error()
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects defense-in-depth standard HTTP security headers on all responses.
    HSTS is intentionally omitted as TLS is terminated by an external reverse proxy.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'"
        )
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )
        return response


class PayloadTooLargeError(Exception):
    """Raised when streaming request body exceeds MAX_REQUEST_BYTES."""

    pass


class RequestSizeLimitMiddleware:
    """
    Pure ASGI middleware enforcing MAX_REQUEST_BYTES on both Content-Length (fast path)
    and streaming chunks from receive() (for chunked or missing Content-Length).
    Rejects oversized requests with HTTP 413 without buffering unlimited memory.
    """

    def __init__(
        self, app: Callable, max_bytes: int = config.MAX_REQUEST_BYTES
    ) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Fast path check on Content-Length header
        headers = dict(scope.get("headers", []))
        raw_cl = headers.get(b"content-length")
        if raw_cl is not None:
            try:
                content_length = int(raw_cl.decode("latin1"))
                if content_length > self.max_bytes:
                    response = JSONResponse(
                        status_code=HTTP_413_CONTENT_TOO_LARGE,
                        content={
                            "detail": (
                                f"Payload size exceeds maximum allowed limit of "
                                f"{self.max_bytes} bytes."
                            )
                        },
                    )
                    await response(scope, receive, send)
                    return
                if content_length < 0:
                    response = JSONResponse(
                        status_code=HTTP_413_CONTENT_TOO_LARGE,
                        content={"detail": "Negative Content-Length header rejected."},
                    )
                    await response(scope, receive, send)
                    return
            except ValueError:
                response = JSONResponse(
                    status_code=HTTP_413_CONTENT_TOO_LARGE,
                    content={"detail": "Malformed Content-Length header."},
                )
                await response(scope, receive, send)
                return

        # Chunked or missing Content-Length: read stream with strict byte limit
        buffered_messages: list[Message] = []
        total_bytes = 0
        while True:
            message = await receive()
            buffered_messages.append(message)
            if message["type"] == "http.request":
                total_bytes += len(message.get("body", b""))
                if total_bytes > self.max_bytes:
                    response = JSONResponse(
                        status_code=HTTP_413_CONTENT_TOO_LARGE,
                        content={
                            "detail": (
                                f"Payload size exceeds maximum allowed limit of "
                                f"{self.max_bytes} bytes."
                            )
                        },
                    )
                    await response(scope, receive, send)
                    return
                if not message.get("more_body", False):
                    break

        # Replay validated body chunks to downstream application
        msg_idx = 0

        async def replay_receive() -> Message:
            nonlocal msg_idx
            if msg_idx < len(buffered_messages):
                msg = buffered_messages[msg_idx]
                msg_idx += 1
                return msg
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay_receive, send)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate limiter per client IP with bounded memory cache (LRU eviction).
    Returns HTTP 429 when rate limit is exceeded.
    """

    def __init__(self, app: Callable) -> None:
        super().__init__(app)
        self.requests: OrderedDict[str, List[float]] = OrderedDict()
        self._lock = threading.Lock()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Bypass rate limiting in test environment to avoid test flakiness
        if config.ENVIRONMENT == "test":
            return await call_next(request)

        client_ip = get_client_ip(request)
        now = time.time()
        window_start = now - 60.0

        with self._lock:
            # Move key to end (most recently used) if already present
            if client_ip in self.requests:
                self.requests.move_to_end(client_ip)

            # Purge timestamps outside sliding window
            active_timestamps = [
                ts for ts in self.requests.get(client_ip, []) if ts > window_start
            ]
            self.requests[client_ip] = active_timestamps

            if len(self.requests[client_ip]) >= config.RATE_LIMIT_PER_MINUTE:
                return JSONResponse(
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Rate limit exceeded. Please retry after some time."
                    },
                    headers={
                        "Retry-After": "60",
                        "X-RateLimit-Limit": str(config.RATE_LIMIT_PER_MINUTE),
                        "X-RateLimit-Remaining": "0",
                    },
                )

            self.requests[client_ip].append(now)

            # Evict least-recently-used IPs if maximum entries threshold is reached
            while len(self.requests) > config.MAX_RATE_LIMIT_ENTRIES:
                self.requests.popitem(last=False)

            remaining = max(
                0, config.RATE_LIMIT_PER_MINUTE - len(self.requests[client_ip])
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(config.RATE_LIMIT_PER_MINUTE)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
