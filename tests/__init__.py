"""Tests package for PyServe AI API."""

import os

# Keep test credentials explicit; application defaults fail closed in production.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("API_KEY", "test-secret-key-that-is-at-least-32-chars-long")
