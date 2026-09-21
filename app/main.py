from typing import Any

import os

import httpx
from fastapi import FastAPI, HTTPException
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


class ScoringResponse(BaseModel):
    application_id: str
    records: list[dict[str, Any]]


SUPABASE_URL = os.getenv("SUPABASE_URL", "https://supabase.mlops.itlabs.io").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


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


@app.get("/v1/scoring/{application_id}", response_model=ScoringResponse)
def get_scoring(application_id: str) -> ScoringResponse:
    """Return all scoring records for one credit application."""
    if not SUPABASE_KEY:
        raise HTTPException(
            status_code=500,
            detail="SUPABASE_KEY is not configured",
        )

    try:
        response = httpx.get(
            f"{SUPABASE_URL}/rest/v1/DONE_REQUEST_SCORES_test",
            params={
                "select": "scoringRole,opinion",
                "id": f"eq.{application_id}",
            },
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            },
            timeout=10.0,
        )
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach Supabase: {error}",
        ) from error

    if response.is_error:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Supabase request failed",
                "status_code": response.status_code,
                "response": response.text[:500],
            },
        )

    records = response.json()
    if not records:
        raise HTTPException(
            status_code=404,
            detail=f"Credit application '{application_id}' was not found",
        )

    return ScoringResponse(
        application_id=application_id,
        records=records,
    )
