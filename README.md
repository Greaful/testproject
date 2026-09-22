# SAP Credit Application Data Service

Локальный HTTP-сервис принимает Excel-файл в Base64, отправляет содержимое в корпоративный AI-провайдер через LiteLLM и возвращает массив кредитных заявок в JSON для SAP.

## Что нужно установить

- Python 3.12+ для запуска без Docker
- Docker Desktop для контейнерного запуска
- Git для публикации в корпоративный репозиторий

## Запуск без Docker

В PowerShell из корня проекта:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
pytest
uvicorn app.main:app --reload
```

Перед запуском задайте параметры AI-провайдера в текущем окне PowerShell:

```powershell
$env:AI_API_URL = "https://litellm.mlops.itlabs.io"
$env:AI_API_KEY = "<твой-ключ>"
$env:AI_MODEL = "gpt-5.6-luna"
```

Откройте <http://127.0.0.1:8000/docs>. Это автоматически созданная страница для проверки API.

Проверка health endpoint:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Проверка Excel endpoint через Swagger:

Откройте <http://127.0.0.1:8000/docs>, выберите `POST /v1/excel/parse`, нажмите `Try it out` и передайте JSON с Base64-файлом.

## Запуск в Docker

```powershell
docker build -t sap-ai-data-service:local .
docker run --rm -p 8000:8000 sap-ai-data-service:local
```

Затем откройте <http://127.0.0.1:8000/docs>.

## Что делать с Git

```powershell
git init
git add .
git commit -m "Initial service prototype"
git remote add origin <URL-вашего-корпоративного-репозитория>
git push -u origin main
```

В реальном корпоративном репозитории обычно нужно создать проект, настроить права, CI/CD и секреты. Секреты AI-провайдера нельзя помещать в Git или Dockerfile: их передают через Secret/Environment Variable на платформе развертывания.

## API

`POST /v1/excel/parse` принимает JSON:

```json
{
    "file_name": "credit-application.xlsx",
    "file_base64": "UEsDB..."
}
```

Поддерживаются файлы `.xlsx` и `.xlsm`. Максимальный размер исходного Excel-файла после декодирования Base64: **10 MB**.

Ответ:

```json
{
    "applications": [
        {
            "name": "ООО ГМ Групп",
            "inn": 9722045906,
            "client_id": 4711,
            "requested_limit": 500000,
            "approved_limit": 400000,
            "start_date": "08.09.2026",
            "end_date": "13.10.2026",
            "bukrs": 1033
        }
    ]
}
```

Правила обработки:

- `inn`, `client_id` и `approved_limit` должны быть непустыми и отличаться от нуля;
- заявки, не соответствующие этим правилам, не возвращаются;
- `requested_limit`, `start_date`, `end_date` и `bukrs` могут быть `null`;
- названия и порядок столбцов Excel могут отличаться.

Ключ AI-провайдера нельзя помещать в Git, Dockerfile или исходный код. Передавай его через environment variable или корпоративный Secret Manager.
