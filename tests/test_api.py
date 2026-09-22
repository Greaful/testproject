import base64
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def _excel_file() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Поле", "Значение"])
    sheet.append(["Балансовая единица", 1033])
    sheet.append(["Название организации", "ООО ГМ Групп"])
    sheet.append(["ИНН", 9722045906])
    sheet.append(["Окончание действия", "13.10.2026"])
    sheet.append(["Одобренный лимит", "400 000"])
    sheet.append(["Начало действия", "08.09.2026"])
    sheet.append(["Запрошенный лимит", "500000"])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _excel_request() -> dict[str, str]:
    return {
        "file_name": "credit-application.xlsx",
        "file_base64": base64.b64encode(_excel_file()).decode("ascii"),
    }


def test_parse_excel_extracts_fields_without_fixed_column_order(monkeypatch) -> None:
    class FakeResponse:
        is_error = False

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '```json\n{"applications":[{"name":"ООО ГМ Групп",'
                                '"inn":9722045906,"client_id":4711,"requested_limit":500000,'
                                '"approved_limit":400000,"start_date":"08.09.2026",'
                                '"end_date":"13.10.2026","bukrs":1033}]}\n```'
                            )
                        }
                    }
                ]
            }

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            assert kwargs["json"]["model"] == "gpt-5.6-luna"
            assert "temperature" not in kwargs["json"]
            return FakeResponse()

    monkeypatch.setattr("app.main.AI_API_KEY", "test-key")
    monkeypatch.setattr("app.main.httpx.AsyncClient", lambda **kwargs: FakeAsyncClient())

    response = client.post(
        "/v1/excel/parse",
        json=_excel_request(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "applications": [{
            "name": "ООО ГМ Групп",
            "inn": 9722045906,
            "client_id": 4711,
            "requested_limit": 500000,
            "approved_limit": 400000,
            "start_date": "08.09.2026",
            "end_date": "13.10.2026",
            "bukrs": 1033,
        }],
    }


def test_parse_excel_rejects_non_excel_file() -> None:
    response = client.post(
        "/v1/excel/parse",
        json={"file_name": "input.txt", "file_base64": "bm90IGV4Y2Vs"},
    )

    assert response.status_code == 415


def test_parse_excel_rejects_files_over_10_mb() -> None:
    response = client.post(
        "/v1/excel/parse",
        json={
            "file_name": "large.xlsx",
            "file_base64": base64.b64encode(b"x" * (10 * 1024 * 1024 + 1)).decode("ascii"),
        },
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "Размер Excel-файла не должен превышать 10 МБ"}


def test_parse_excel_excludes_applications_with_zero_approved_limit(monkeypatch) -> None:
    class FakeResponse:
        is_error = False

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"applications":['
                                '{"name":"Approved","inn":1,"client_id":10,"requested_limit":100,'
                                '"approved_limit":50,"start_date":"08.09.2026",'
                                '"end_date":"13.10.2026","bukrs":1033},'
                                '{"name":"Rejected","inn":2,"client_id":0,"requested_limit":100,'
                                '"approved_limit":0,"start_date":null,'
                                '"end_date":null,"bukrs":null}]}'
                            )
                        }
                    }
                ]
            }

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("app.main.AI_API_KEY", "test-key")
    monkeypatch.setattr("app.main.httpx.AsyncClient", lambda **kwargs: FakeAsyncClient())

    response = client.post(
        "/v1/excel/parse",
        json=_excel_request(),
    )

    assert response.status_code == 200
    assert [application["name"] for application in response.json()["applications"]] == ["Approved"]
