import unittest
from app.main import app
from app.services.model_service import get_model_service
from tests.test_helpers import asgi_json_request, perform_asgi_request


class TestHeartbeatEndpoint(unittest.TestCase):
    def test_heartbeat_success(self) -> None:
        status, body = asgi_json_request(app, "GET", "/api/health/heartbeat")
        self.assertEqual(status, 200)
        self.assertIsInstance(body, dict)
        self.assertEqual(body, {"is_alive": True})

    def test_readiness_transitions(self) -> None:
        service = get_model_service()

        # Unloaded state -> 503
        service.unload()
        status, body = asgi_json_request(app, "GET", "/api/health/ready")
        self.assertEqual(status, 503)
        self.assertEqual(body, {"is_ready": False})

        # Loaded state -> 200
        service.load()
        status, body = asgi_json_request(app, "GET", "/api/health/ready")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"is_ready": True})

    def test_metrics_endpoint_success(self) -> None:
        status, body = asgi_json_request(app, "GET", "/api/health/metrics")
        self.assertEqual(status, 200)
        self.assertIn("worker_pid", body)
        self.assertIn("uptime_seconds", body)
        self.assertIn("total_requests", body)
        self.assertIn("total_predictions", body)
        self.assertIn("total_errors", body)
        self.assertIn("model_loaded", body)

    def test_security_headers_present(self) -> None:
        status, headers, _ = perform_asgi_request(app, "GET", "/api/health/heartbeat")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(headers.get("x-frame-options"), "DENY")
        self.assertEqual(headers.get("referrer-policy"), "no-referrer")
        self.assertEqual(
            headers.get("content-security-policy"),
            "default-src 'none'; frame-ancestors 'none'",
        )
        self.assertIn("camera=()", headers.get("permissions-policy", ""))

    def test_correlation_id_propagated(self) -> None:
        # Pre-set correlation ID
        status, headers, _ = perform_asgi_request(
            app,
            "GET",
            "/api/health/heartbeat",
            headers={"X-Request-ID": "custom-trace-id-12345"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers["x-request-id"], "custom-trace-id-12345")

        # Auto-generated correlation ID
        status, headers, _ = perform_asgi_request(app, "GET", "/api/health/heartbeat")
        self.assertEqual(status, 200)
        self.assertIn("x-request-id", headers)
        self.assertTrue(len(headers["x-request-id"]) > 0)


if __name__ == "__main__":
    unittest.main()
