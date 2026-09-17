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
    data: list[dict] | None = None
    columns: list[str] | None = None


class HealthResponse(BaseModel):
    status: str
    rows: int
    columns: list[str]


# ---------------------------------------------------------------- helpers

def _records_json_safe(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to a list of JSON-safe dicts (NaN → None, Timestamp → ISO string)."""
    records = []
    for _, row in df.iterrows():
        rec = {}
        for col in df.columns:
            val = row[col]
            if pd.isna(val):
                rec[col] = None
            elif isinstance(val, pd.Timestamp):
                rec[col] = val.isoformat()
            else:
                rec[col] = val
        records.append(rec)
    return records


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
    records = _records_json_safe(df)
    return {"count": len(records), "tickets": records}