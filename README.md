# SAP AI Data Service

Первый локальный прототип HTTP-сервиса. Он принимает JSON от SAP, передает его во временный mock-провайдер и возвращает результат. Подключение корпоративного AI API будет следующим шагом.

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

Откройте <http://127.0.0.1:8000/docs>. Это автоматически созданная страница для проверки API.

Проверка health endpoint:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Проверка extraction endpoint:

```powershell
$body = @{
    instruction = "Extract the delivery status"
    data = @{
        delivery_id = "4711"
        status = "SHIPPED"
    }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/extract -ContentType "application/json" -Body $body
```

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

## Текущие ограничения

- Ответ пока не генерирует настоящая AI-модель: используется `provider=mock`.
- Supabase endpoint требует переменные окружения `SUPABASE_URL` и `SUPABASE_KEY`.
- Аутентификация, лимиты запросов, журналирование и подключение к корпоративному AI API еще не добавлены.
- В Kubernetes этот контейнер можно будет развернуть после получения требований компании к namespace, ingress, ресурсам, secrets и health probes.
