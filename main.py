"""
FastAPI application exposing the support-ticket AI system.

Endpoints:
  GET /health              — liveness probe
  GET /query?q=...         — natural language question
  GET /anomalies           — anomaly report
  GET /tickets             — raw ticket list (with optional filters)
"""

from functools import lru_cache

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from data_loader import load_tickets
from query_engine import answer_question
from anomaly import detect_anomalies

app = FastAPI(
    title="Support Ticket AI",
    description="NL querying + anomaly detection over the support tickets CSV.",
    version="1.0.0",
)


# ---------------------------------------------------------------- data cache

@lru_cache(maxsize=1)
def get_df() -> pd.DataFrame:
    """Load the CSV once and cache it for the process lifetime."""
    return load_tickets()


# ---------------------------------------------------------------- models

class QueryResponse(BaseModel):
    question: str
    plan: dict | None
    answer: str


class HealthResponse(BaseModel):
    status: str
    rows: int
    columns: list[str]


# ---------------------------------------------------------------- endpoints

@app.get("/health", response_model=HealthResponse)
def health():
    df = get_df()
    return HealthResponse(status="ok", rows=len(df), columns=df.columns.tolist())


@app.get("/query", response_model=QueryResponse)
def query(q: str = Query(..., min_length=2, description="Natural language question")):
    df = get_df()
    result = answer_question(q, df)
    if result.get("plan") is None and result["answer"].startswith("Error"):
        raise HTTPException(status_code=500, detail=result["answer"])
    return QueryResponse(**result)


@app.get("/anomalies")
def anomalies():
    df = get_df()
    return detect_anomalies(df)


@app.get("/tickets")
def tickets(
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    limit: int = 20,
):
    df = get_df()
    if status:
        df = df[df["status"] == status]
    if priority:
        df = df[df["priority"] == priority]
    if category:
        df = df[df["category"] == category]
    df = df.head(limit)
    # Convert NaN → None for JSON compliance
    records = df.where(pd.notna(df), None).to_dict(orient="records")
    for rec in records:
        if isinstance(rec.get("created_at"), pd.Timestamp):
            rec["created_at"] = rec["created_at"].isoformat()
    return {"count": len(records), "tickets": records}