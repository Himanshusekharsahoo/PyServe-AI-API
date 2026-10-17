import unittest
from unittest.mock import patch

import tests.test_helpers  # noqa: F401
from app.core import config


class TestConfiguration(unittest.TestCase):
    def test_default_config_values(self) -> None:
        self.assertEqual(config.APP_NAME, "PyServe AI API")
        self.assertEqual(config.API_PREFIX, "/api")
        self.assertTrue(len(config.APP_VERSION) > 0)
        self.assertIn("sentiment", config.DEFAULT_MODEL_PATH)
        self.assertIsInstance(config.IS_DEBUG, bool)

    def test_validate_config_success(self) -> None:
        # Test-mode configuration should pass validation
        try:
            config.validate_config()
        except ValueError as e:
            self.fail(f"validate_config() raised ValueError unexpectedly: {e}")

    def test_api_key_accessible(self) -> None:
        self.assertIsNotNone(config.API_KEY)
        self.assertGreater(len(str(config.API_KEY)), 0)

    def test_production_requires_strong_key(self) -> None:
        with (
            patch("app.core.config.ENVIRONMENT", "production"),
            patch("app.core.config.API_KEY", None),
            self.assertRaises(ValueError),
        ):
            config.validate_config()

    def test_production_rejects_placeholder_keys(self) -> None:
        with (
            patch("app.core.config.ENVIRONMENT", "production"),
            patch("app.core.config.API_KEY", "sample_api_key_sample_api_key_32c"),
            self.assertRaises(ValueError),
        ):
            config.validate_config()

    def test_invalid_environment_rejected(self) -> None:
        with (
            patch("app.core.config.ENVIRONMENT", "staging"),
            self.assertRaises(ValueError),
        ):
            config.validate_config()

    def test_wildcard_cors_rejected_in_production(self) -> None:
        with (
            patch("app.core.config.ENVIRONMENT", "production"),
            patch("app.core.config.API_KEY", "super_secure_production_token_12345"),
            patch("app.core.config.ALLOWED_ORIGINS", ["*"]),
            self.assertRaises(ValueError),
        ):
            config.validate_config()

    def test_production_rejects_invalid_or_missing_model_sha256(self) -> None:
        # Invalid hash format
        with (
            patch("app.core.config.ENVIRONMENT", "production"),
            patch("app.core.config.API_KEY", "super_secure_production_token_12345"),
            patch("app.core.config.EXPECTED_MODEL_SHA256", "invalid-short-hash"),
            self.assertRaises(ValueError),
        ):
            config.validate_config()

        # Missing hash
        with (
            patch("app.core.config.ENVIRONMENT", "production"),
            patch("app.core.config.API_KEY", "super_secure_production_token_12345"),
            patch("app.core.config.EXPECTED_MODEL_SHA256", None),
            self.assertRaises(ValueError),
        ):
            config.validate_config()

    def test_rate_limit_entries_must_be_positive(self) -> None:
        with (
            patch("app.core.config.MAX_RATE_LIMIT_ENTRIES", 0),
            self.assertRaises(ValueError),
        ):
            config.validate_config()


if __name__ == "__main__":
    unittest.main()
