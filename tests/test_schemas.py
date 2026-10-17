import unittest

import tests.test_helpers  # noqa: F401
from pydantic import ValidationError

from app.models.heartbeat import (
    HearbeatResult,
    HeartbeatResult,
    MetricsResult,
    ReadinessResult,
)
from app.models.payload import TextPayload
from app.models.prediction import PredictionResponse


class TestSchemas(unittest.TestCase):
    def test_text_payload_valid(self) -> None:
        payload = TextPayload(text="  This is a great product!  ")
        # Ensure whitespace stripping validator works
        self.assertEqual(payload.text, "This is a great product!")

    def test_text_payload_rejects_empty(self) -> None:
        with self.assertRaises(ValidationError):
            TextPayload(text="")

    def test_text_payload_rejects_whitespace_only(self) -> None:
        with self.assertRaises(ValidationError):
            TextPayload(text="     ")

    def test_text_payload_rejects_excessive_length(self) -> None:
        with self.assertRaises(ValidationError):
            TextPayload(text="a" * 5001)

    def test_prediction_response_valid(self) -> None:
        resp = PredictionResponse(sentiment="positive", confidence=0.985)
        self.assertEqual(resp.sentiment, "positive")
        self.assertEqual(resp.confidence, 0.985)

    def test_prediction_response_confidence_bounds(self) -> None:
        # Confidence must be between 0.0 and 1.0
        with self.assertRaises(ValidationError):
            PredictionResponse(sentiment="positive", confidence=1.5)

        with self.assertRaises(ValidationError):
            PredictionResponse(sentiment="negative", confidence=-0.1)

    def test_heartbeat_result_valid(self) -> None:
        hb = HeartbeatResult(is_alive=True)
        self.assertTrue(hb.is_alive)
        # Verify alias
        self.assertIs(HearbeatResult, HeartbeatResult)

    def test_readiness_result_valid(self) -> None:
        rr = ReadinessResult(is_ready=True)
        self.assertTrue(rr.is_ready)

    def test_metrics_result_valid(self) -> None:
        mr = MetricsResult(
            worker_pid=1234,
            uptime_seconds=12.34,
            total_requests=10,
            total_predictions=5,
            total_errors=1,
            model_loaded=True,
        )
        self.assertEqual(mr.worker_pid, 1234)
        self.assertEqual(mr.total_requests, 10)
        self.assertTrue(mr.model_loaded)


if __name__ == "__main__":
    unittest.main()
