import asyncio
import unittest
from typing import Any
from unittest.mock import patch

import tests.test_helpers  # noqa: F401
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.core import config
from app.main import create_app, get_app
from tests.test_helpers import perform_asgi_request


class TestAppArchitecture(unittest.TestCase):
    def test_app_factory(self) -> None:
        app = create_app()
        self.assertIsInstance(app, FastAPI)
        self.assertEqual(app.title, config.APP_NAME)
        self.assertEqual(app.version, config.APP_VERSION)
        # Test alias
        self.assertIs(get_app, create_app)

    def test_routes_registered(self) -> None:
        app = create_app()
        registered_paths = app.openapi()["paths"]
        self.assertIn("/api/health/heartbeat", registered_paths)
        self.assertIn("/api/model/predict", registered_paths)
        self.assertIn("/api/health/ready", registered_paths)
        self.assertIn("/api/health/metrics", registered_paths)

    def test_cors_uses_explicit_origins_with_credentials(self) -> None:
        cors = next(m for m in create_app().user_middleware if m.cls is CORSMiddleware)
        self.assertEqual(cors.kwargs["allow_origins"], config.ALLOWED_ORIGINS)
        self.assertTrue(cors.kwargs["allow_credentials"])

    def test_cors_preflight_allows_only_configured_origin(self) -> None:
        status, headers, _ = perform_asgi_request(
            create_app(),
            "OPTIONS",
            "/api/model/predict",
            headers={
                "origin": config.ALLOWED_ORIGINS[0],
                "access-control-request-method": "POST",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(
            headers["access-control-allow-origin"], config.ALLOWED_ORIGINS[0]
        )
        self.assertEqual(headers["access-control-allow-credentials"], "true")

    def test_cors_preflight_rejects_untrusted_origin(self) -> None:
        status, headers, _ = perform_asgi_request(
            create_app(),
            "OPTIONS",
            "/api/model/predict",
            headers={
                "origin": "http://malicious-website.com",
                "access-control-request-method": "POST",
            },
        )
        self.assertNotIn("access-control-allow-origin", headers)

    def test_payload_exceeding_max_bytes_returns_413(self) -> None:
        oversized_len = str(config.MAX_REQUEST_BYTES + 1024)
        status, headers, body = perform_asgi_request(
            create_app(),
            "POST",
            "/api/model/predict",
            headers={"content-length": oversized_len},
            body=b"x" * 100,
        )
        self.assertEqual(status, 413)
        self.assertIn("x-request-id", headers)
        self.assertTrue(len(headers["x-request-id"]) > 0)

    def test_rate_limiting_enforced(self) -> None:
        with (
            patch.object(config, "ENVIRONMENT", "production"),
            patch.object(config, "RATE_LIMIT_PER_MINUTE", 2),
        ):
            app = create_app()
            status1, _, _ = perform_asgi_request(app, "GET", "/api/health/heartbeat")
            status2, _, _ = perform_asgi_request(app, "GET", "/api/health/heartbeat")
            status3, headers3, body3 = perform_asgi_request(
                app, "GET", "/api/health/heartbeat"
            )
            self.assertEqual(status1, 200)
            self.assertEqual(status2, 200)
            self.assertEqual(status3, 429)
            self.assertIn("Rate limit exceeded", body3.decode())
            self.assertIn("x-request-id", headers3)
            self.assertEqual(headers3.get("retry-after"), "60")

    def test_lifecycle_handlers(self) -> None:
        app = create_app()

        async def exercise_lifespan() -> None:
            async with app.router.lifespan_context(app):
                self.assertTrue(app.state.model_service.is_loaded)

        asyncio.run(exercise_lifespan())
        self.assertIsNone(app.state.model_service)

    def test_chunked_streaming_payload_exceeding_max_bytes_returns_413(
        self,
    ) -> None:
        oversized_body = b"y" * (config.MAX_REQUEST_BYTES + 500)
        # Omit content-length header to simulate chunked/streaming payload
        status, headers, body = perform_asgi_request(
            create_app(),
            "POST",
            "/api/model/predict",
            headers={"content-type": "application/json"},
            body=oversized_body,
        )
        self.assertEqual(status, 413)
        self.assertIn("x-request-id", headers)
        self.assertIn("Payload size exceeds maximum allowed limit", body.decode())

    def test_malformed_and_negative_content_length_returns_413(self) -> None:
        app = create_app()
        # Malformed non-numeric
        s1, _, b1 = perform_asgi_request(
            app,
            "POST",
            "/api/model/predict",
            headers={"content-length": "not-a-number"},
            body=b"test",
        )
        self.assertEqual(s1, 413)
        self.assertIn("Malformed Content-Length", b1.decode())

        # Negative content length
        s2, _, b2 = perform_asgi_request(
            app,
            "POST",
            "/api/model/predict",
            headers={"content-length": "-10"},
            body=b"test",
        )
        self.assertEqual(s2, 413)
        self.assertIn("Negative Content-Length", b2.decode())

    def test_correlation_id_sanitized_when_malformed(self) -> None:
        app = create_app()
        # Malformed XSS payload in correlation ID
        s1, h1, _ = perform_asgi_request(
            app,
            "GET",
            "/api/health/heartbeat",
            headers={"X-Request-ID": "<script>alert(1)</script>"},
        )
        self.assertEqual(s1, 200)
        self.assertIn("x-request-id", h1)
        self.assertNotIn("<script>", h1["x-request-id"])
        self.assertEqual(len(h1["x-request-id"]), 36)  # UUID4 length

        # Valid correlation ID preserved
        s2, h2, _ = perform_asgi_request(
            app,
            "GET",
            "/api/health/heartbeat",
            headers={"X-Request-ID": "valid-trace-id-12345"},
        )
        self.assertEqual(s2, 200)
        self.assertEqual(h2.get("x-request-id"), "valid-trace-id-12345")

    def test_rate_limiter_evicts_lru_when_capacity_reached(self) -> None:
        from app.core.middleware import RateLimitMiddleware

        with (
            patch.object(config, "ENVIRONMENT", "production"),
            patch.object(config, "MAX_RATE_LIMIT_ENTRIES", 2),
        ):
            app = create_app()
            # Find RateLimitMiddleware instance
            rate_middleware = None
            curr: Any = app.middleware_stack
            while curr is not None:
                if isinstance(curr, RateLimitMiddleware):
                    rate_middleware = curr
                    break
                curr = getattr(curr, "app", None)

            # Simulate requests from 3 distinct IPs
            for ip in ("10.0.0.1", "10.0.0.2", "10.0.0.3"):
                perform_asgi_request(
                    app,
                    "GET",
                    "/api/health/heartbeat",
                    headers={"X-Forwarded-For": ip},
                )

            if rate_middleware:
                self.assertLessEqual(len(rate_middleware.requests), 2)

    def test_trusted_proxy_resolution_vs_untrusted_spoofing(self) -> None:
        from fastapi import Request
        from app.core.security import get_client_ip

        # Case 1: Direct untrusted client attempting spoofing
        with patch.object(config, "TRUSTED_PROXIES", []):
            scope1: dict[str, Any] = {
                "type": "http",
                "client": ("203.0.113.5", 12345),
                "headers": [(b"x-forwarded-for", b"198.51.100.2")],
            }
            req1 = Request(scope1)
            self.assertEqual(get_client_ip(req1), "203.0.113.5")

        # Case 2: Trusted reverse proxy forwarding real client IP
        with patch.object(config, "TRUSTED_PROXIES", ["127.0.0.1", "10.0.0.1"]):
            scope2: dict[str, Any] = {
                "type": "http",
                "client": ("10.0.0.1", 12345),
                "headers": [(b"x-forwarded-for", b"198.51.100.2, 10.0.0.1")],
            }
            req2 = Request(scope2)
            self.assertEqual(get_client_ip(req2), "198.51.100.2")

    def test_api_documentation_disabled_in_production(self) -> None:
        with patch.object(config, "ENVIRONMENT", "production"):
            prod_app = create_app()
            self.assertIsNone(prod_app.docs_url)
            self.assertIsNone(prod_app.redoc_url)
            self.assertIsNone(prod_app.openapi_url)
            status, _, _ = perform_asgi_request(prod_app, "GET", "/docs")
            self.assertEqual(status, 404)

    def test_api_documentation_enabled_in_development(self) -> None:
        with patch.object(config, "ENVIRONMENT", "development"):
            dev_app = create_app()
            self.assertEqual(dev_app.docs_url, "/docs")
            status, _, _ = perform_asgi_request(dev_app, "GET", "/docs")
            self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
