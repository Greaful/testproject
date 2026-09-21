from fastapi.testclient import TestClient

from app import main


client = TestClient(main.app)


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


def test_scoring_returns_all_records(monkeypatch) -> None:
    class FakeResponse:
        is_error = False

        def json(self):
            return [
                {"scoringRole": "CREDIT", "opinion": "APPROVE"},
                {"scoringRole": "RISK", "opinion": "REVIEW"},
            ]

    def fake_get(*args, **kwargs):
        assert args[0].endswith("/rest/v1/DONE_REQUEST_SCORES_test")
        assert kwargs["params"] == {
            "select": "scoringRole,opinion",
            "id": "eq.4711",
        }
        return FakeResponse()

    monkeypatch.setattr(main, "SUPABASE_KEY", "test-key")
    monkeypatch.setattr(main.httpx, "get", fake_get)

    response = client.get("/v1/scoring/4711")

    assert response.status_code == 200
    assert response.json() == {
        "application_id": "4711",
        "records": [
            {"scoringRole": "CREDIT", "opinion": "APPROVE"},
            {"scoringRole": "RISK", "opinion": "REVIEW"},
        ],
    }


def test_scoring_returns_404_when_application_is_missing(monkeypatch) -> None:
    class FakeResponse:
        is_error = False

        def json(self):
            return []

    monkeypatch.setattr(main, "SUPABASE_KEY", "test-key")
    monkeypatch.setattr(main.httpx, "get", lambda *args, **kwargs: FakeResponse())

    response = client.get("/v1/scoring/9999")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Credit application '9999' was not found"
    }


def test_scoring_requires_supabase_key(monkeypatch) -> None:
    monkeypatch.setattr(main, "SUPABASE_KEY", None)

    response = client.get("/v1/scoring/4711")

    assert response.status_code == 500
    assert response.json() == {"detail": "SUPABASE_KEY is not configured"}
