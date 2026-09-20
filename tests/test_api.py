from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_extract_returns_received_data() -> None:
    response = client.post(
        "/v1/extract",
        json={
            "instruction": "Extract the delivery status",
            "data": {"delivery_id": "4711", "status": "SHIPPED"},
        },
    )

    assert response.status_code == 200
    assert response.json()["provider"] == "mock"
    assert response.json()["result"]["received_data"]["delivery_id"] == "4711"
