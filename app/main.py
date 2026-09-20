from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field


app = FastAPI(
    title="SAP AI Data Service",
    version="0.1.0",
    description="Receives structured data and returns an AI-ready extraction result.",
)


class ExtractionRequest(BaseModel):
    instruction: str = Field(min_length=1, description="What should be extracted")
    data: Any = Field(description="Data received from SAP")


class ExtractionResponse(BaseModel):
    result: dict[str, Any]
    provider: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/extract", response_model=ExtractionResponse)
def extract(request: ExtractionRequest) -> ExtractionResponse:
    """Temporary deterministic provider used until the corporate AI API is connected."""
    return ExtractionResponse(
        result={
            "message": "Mock response. Corporate AI provider is not connected yet.",
            "instruction": request.instruction,
            "received_data": request.data,
        },
        provider="mock",
    )
