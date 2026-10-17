import os
import tempfile
import unittest
from typing import List

import tests.test_helpers  # noqa: F401
from app.core import config
from app.main import app
from app.services.model_service import (
    ModelLoadError,
    SentimentModelService,
    get_model_service,
)
from tests.test_helpers import asgi_json_request


class MockSentimentClassifier:
    """Mock model used strictly for testing the pipeline end-to-end."""

    classes_ = ["negative", "positive"]

    def predict(self, texts: List[str]) -> List[str]:
        return ["positive"]

    def predict_proba(self, texts: List[str]) -> List[List[float]]:
        return [[0.08, 0.92]]


class TestPredictionEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.auth_headers = {"token": str(config.API_KEY)}
        self.service = get_model_service()
        self.service.unload()

    def tearDown(self) -> None:
        self.service.unload()

    def test_missing_auth_header_returns_401(self) -> None:
        status, body = asgi_json_request(
            app,
            "POST",
            "/api/model/predict",
            headers={},
            json_data={"text": "Excellent service!"},
        )
        self.assertEqual(status, 401)
        self.assertIn("detail", body)
        self.assertEqual(body["detail"], "Authentication required.")

    def test_invalid_auth_token_returns_401(self) -> None:
        status, body = asgi_json_request(
            app,
            "POST",
            "/api/model/predict",
            headers={"token": "incorrect_token_123"},
            json_data={"text": "Excellent service!"},
        )
        self.assertEqual(status, 401)
        self.assertIn("detail", body)
        self.assertEqual(body["detail"], "Authentication required.")

    def test_invalid_payload_returns_422(self) -> None:
        # Blank / whitespace-only string violates TextPayload validator
        status, body = asgi_json_request(
            app,
            "POST",
            "/api/model/predict",
            headers=self.auth_headers,
            json_data={"text": "   "},
        )
        self.assertEqual(status, 422)

        # Missing required field 'text'
        status, body = asgi_json_request(
            app,
            "POST",
            "/api/model/predict",
            headers=self.auth_headers,
            json_data={"message": "No text key"},
        )
        self.assertEqual(status, 422)

    def test_prediction_when_model_unloaded_returns_503(self) -> None:
        # Service has no model loaded; should return 503 rather than faking
        status, body = asgi_json_request(
            app,
            "POST",
            "/api/model/predict",
            headers=self.auth_headers,
            json_data={"text": "Testing with no model loaded."},
        )
        self.assertEqual(status, 503)
        self.assertIn("Inference unavailable", body["detail"])

    def test_prediction_with_mocked_model_returns_200(self) -> None:
        # Inject mock model to verify endpoint wiring and schema serialization
        self.service.set_model(MockSentimentClassifier())

        status, body = asgi_json_request(
            app,
            "POST",
            "/api/model/predict",
            headers=self.auth_headers,
            json_data={"text": "This is a really good experience."},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["sentiment"], "positive")
        self.assertEqual(body["confidence"], 0.92)

    def test_real_artifact_inference_returns_model_probability(self) -> None:
        self.service.load()
        # Positive sentiment test
        status, body = asgi_json_request(
            app,
            "POST",
            "/api/model/predict",
            headers=self.auth_headers,
            json_data={"text": "This product is excellent and I love it."},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["sentiment"], "positive")
        self.assertGreater(body["confidence"], 0.5)
        self.assertLessEqual(body["confidence"], 1.0)

        # Negative sentiment test
        status_neg, body_neg = asgi_json_request(
            app,
            "POST",
            "/api/model/predict",
            headers=self.auth_headers,
            json_data={"text": "This product was awful, terrible, and defective."},
        )
        self.assertEqual(status_neg, 200)
        self.assertEqual(body_neg["sentiment"], "negative")
        self.assertGreater(body_neg["confidence"], 0.5)
        self.assertLessEqual(body_neg["confidence"], 1.0)

    def test_incompatible_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_path = os.path.join(tmp_dir, "invalid_model.joblib")
            with open(artifact_path, "wb") as f:
                f.write(b"invalid")
            with self.assertRaises(ModelLoadError):
                SentimentModelService(artifact_path).load()

    def test_digest_mismatch_prevents_deserialization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_path = os.path.join(tmp_dir, "tampered_model.joblib")
            with open(artifact_path, "wb") as f:
                f.write(b"malicious-or-tampered-content")
            fake_hash = (
                "00000000000000000000000000000000" "00000000000000000000000000000000"
            )
            service = SentimentModelService(
                artifact_path,
                expected_sha256=fake_hash,
            )
            with self.assertRaises(ModelLoadError) as ctx:
                service.load()
            self.assertIn("digest mismatch", str(ctx.exception).lower())

    def test_missing_digest_in_production_fails_closed(self) -> None:
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_path = os.path.join(tmp_dir, "prod_model.joblib")
            with open(artifact_path, "wb") as f:
                f.write(b"any-content")
            with (
                patch.object(config, "ENVIRONMENT", "production"),
                patch.object(config, "EXPECTED_MODEL_SHA256", None),
            ):
                service = SentimentModelService(artifact_path, expected_sha256=None)
                with self.assertRaises(ModelLoadError) as ctx:
                    service.load()
                self.assertIn("refusing to deserialize", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
