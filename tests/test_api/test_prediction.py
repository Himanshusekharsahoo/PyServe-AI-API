from starlette.testclient import TestClient

from app.core import config


def test_prediction(test_client: TestClient) -> None:
    response = test_client.post(
        "/api/model/predict",
        json={"text": "The platform is incredibly fast, dependable, and intuitive."},
        headers={"token": str(config.API_KEY)},
    )
    assert response.status_code == 200
    assert response.json()["sentiment"] == "positive"
    assert response.json()["confidence"] > 0.5


def test_prediction_nopayload(test_client: TestClient) -> None:
    response = test_client.post(
        "/api/model/predict", json={}, headers={"token": str(config.API_KEY)}
    )
    assert response.status_code == 422
