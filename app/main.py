import json
import os
import base64
from datetime import date, datetime
from io import BytesIO
from typing import Any

import openpyxl
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


app = FastAPI(
    title="SAP Credit Application Data Service",
    version="0.2.0",
    description="Extracts credit application fields from Excel files.",
)


class CreditApplication(BaseModel):
    name: str
    inn: int | None = None
    client_id: int | None = None
    requested_limit: float | None = None
    approved_limit: float | None = None
    start_date: str | None = None
    end_date: str | None = None
    bukrs: int | None = None


class ExcelRequest(BaseModel):
    file_name: str
    file_base64: str


class CreditApplicationResponse(BaseModel):
    applications: list[CreditApplication]


AI_API_URL = os.getenv("AI_API_URL", "https://litellm.mlops.itlabs.io").rstrip("/")
AI_API_KEY = os.getenv("AI_API_KEY")
AI_MODEL = os.getenv("AI_MODEL", "gpt-5.6-luna")
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/excel/parse", response_model=CreditApplicationResponse)
async def parse_excel(request: ExcelRequest) -> CreditApplicationResponse:
    """Extract credit applications from a Base64-encoded Excel file."""
    if not request.file_name.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(
            status_code=415,
            detail="Поддерживаются только файлы Excel форматов .xlsx и .xlsm",
        )

    try:
        file_content = base64.b64decode(request.file_base64, validate=True)
        if len(file_content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Размер Excel-файла не должен превышать 10 МБ",
            )
        workbook = openpyxl.load_workbook(
            BytesIO(file_content),
            data_only=True,
            read_only=True,
        )
    except (OSError, ValueError, base64.binascii.Error) as error:
        raise HTTPException(
            status_code=400,
            detail="Не удалось прочитать Excel-файл. Проверьте Base64 и содержимое файла",
        ) from error

    values = [
        cell.value
        for sheet in workbook.worksheets
        for row in sheet.iter_rows()
        for cell in row
    ]
    result = await _extract_with_ai(values)
    workbook.close()
    return result


async def _extract_with_ai(values: list[Any]) -> CreditApplicationResponse:
    if not AI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Не настроен ключ доступа к AI-провайдеру",
        )

    table_text = "\n".join(
        f"- Cell {index + 1}: {value}"
        for index, value in enumerate(values)
        if value is not None and str(value).strip()
    )
    prompt = (
        "Extract credit applications from this Excel content. "
        "Column names and order are arbitrary. Each data row is one application. "
        "Ignore title rows, empty rows, totals, and explanatory text. Do not invent values. "
        "Return only valid JSON with this exact shape: "
        '{"applications":[{"name":"...","inn":123,"client_id":123,'
        '"requested_limit":123,"approved_limit":123,"start_date":"DD.MM.YYYY",'
        '"end_date":"DD.MM.YYYY","bukrs":123}]}. '
        "The fields inn, client_id, and approved_limit must be present and non-zero. "
        "Return one object per application row.\n\nExcel content:\n" + table_text
    )

    request_body = {
        "model": AI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You extract structured data and return JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{AI_API_URL}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=request_body,
            )
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail="Не удалось подключиться к AI-провайдеру",
        ) from error

    if response.is_error:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "AI-провайдер отклонил запрос",
                "status_code": response.status_code,
                "response": response.text[:1000],
            },
        )

    try:
        provider_payload = response.json()
        content = provider_payload["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise TypeError("AI message content is not a string")
        content = content.strip()
        if content.startswith("```"):
            content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        payload = json.loads(content)
        if "applications" not in payload:
            payload = {"applications": _columns_to_rows(payload)}
        result = CreditApplicationResponse.model_validate(payload)
        result.applications = [
            application
            for application in result.applications
            if application.inn not in (None, 0)
            and application.client_id not in (None, 0)
            and application.approved_limit not in (None, 0)
        ]
        return result
    except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValueError) as error:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "AI-провайдер вернул данные в неправильном формате",
                "error": f"Не удалось проверить ответ AI: {error}",
                "response": response.text[:1000],
            },
        ) from error


def _columns_to_rows(payload: dict[str, list[Any]]) -> list[dict[str, Any]]:
    if not payload or not all(isinstance(value, list) for value in payload.values()):
        return []
    row_count = max(len(value) for value in payload.values())
    return [
        {field: values[index] if index < len(values) else None for field, values in payload.items()}
        for index in range(row_count)
    ]


def _normalize_text(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.strftime("%d.%m.%Y")
    return " ".join(str(value or "").strip().lower().split())


def _find_text(values: list[Any], normalized: list[str], labels: tuple[str, ...]) -> str:
    for index, value in enumerate(normalized):
        if any(label in value for label in labels):
            for candidate_index in range(index + 1, len(values)):
                if normalized[candidate_index] and not any(
                    label in normalized[candidate_index] for label in labels
                ):
                    return str(values[candidate_index]).strip()
    raise HTTPException(status_code=422, detail=f"Could not find field: {labels[0]}")


def _find_number(values: list[Any], normalized: list[str], labels: tuple[str, ...]) -> int | float:
    value = _find_text(values, normalized, labels).replace(" ", "").replace(",", ".")
    try:
        number = float(value)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=f"Invalid number for field: {labels[0]}") from error
    return int(number) if number.is_integer() else number


def _find_date(values: list[Any], normalized: list[str], labels: tuple[str, ...]) -> str:
    value = _find_text(values, normalized, labels)
    for date_format in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, date_format).strftime("%d.%m.%Y")
        except ValueError:
            continue
    raise HTTPException(status_code=422, detail=f"Invalid date for field: {labels[0]}")
