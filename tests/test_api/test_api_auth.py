from starlette.testclient import TestClient

from app.core import messages


def test_auth_using_prediction_api_no_apikey_header(
    test_client: TestClient,
) -> None:
    response = test_client.post("/api/model/predict")
    assert response.status_code == 401
    assert response.json() == {"detail": messages.AUTH_REQ}


def test_auth_using_prediction_api_wrong_apikey_header(
    test_client: TestClient,
) -> None:
    response = test_client.post(
        "/api/model/predict",
        json={"text": "test"},
        headers={"token": "WRONG_TOKEN"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": messages.AUTH_REQ}
