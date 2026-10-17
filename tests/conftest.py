import os
from typing import Generator

import pytest
from starlette.testclient import TestClient

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("API_KEY", "test-secret-key-that-is-at-least-32-chars-long")
os.environ.setdefault("DEFAULT_MODEL_PATH", "models/sentiment.pkl")

from app.main import get_app  # noqa: E402


@pytest.fixture()
def test_client() -> Generator[TestClient, None, None]:
    app = get_app()
    with TestClient(app) as test_client:
        yield test_client
