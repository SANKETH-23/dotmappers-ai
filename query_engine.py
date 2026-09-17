"""
Natural Language → structured query → DataFrame answer.

Design: the LLM only outputs a small JSON spec (operation, filters, group_by, sort, limit).
Python then applies it to the DataFrame. The LLM never touches raw pandas code.
"""

import json
import re
from typing import Any

import pandas as pd

from llm import ask_llm
from data_loader import load_tickets

# ---------------------------------------------------------------- prompt

SYSTEM_PROMPT = """You are a data query planner for a customer support ticket dataset.

The DataFrame has these columns:
- ticket_id (string)
- created_at (datetime)
- category: Billing | Technical | General
- priority: Low | Medium | High | Critical
- status: Open | Resolved | Escalated
- response_time_hrs (float)
- resolution_time_hrs (float, null if unresolved)
- agent_id (string)
- cust_rating (float, null if unresolved)
- issue_summary (string)

Convert the user's question into ONLY a JSON object with this exact schema:
{
  "operation": "count" | "avg" | "sum" | "min" | "max" | "list" | "groupby_count" | "groupby_avg",
  "target": "<column to aggregate, required for avg/sum/min/max/groupby_avg>",
  "filters": { "<column>": "<value or list>" },
  "group_by": "<column, required for groupby_*>",
  "sort": "asc" | "desc",
  "limit": <integer or null>
}

Rules:
- Use exact column names and values from the dataset.
- For "how many" → operation "count".
- For "average/mean" → operation "avg" with target.
- For "which agent has the most/least" → operation "groupby_count" with group_by "agent_id".
  If the question mentions "resolved", add filter {"status": "Resolved"}.
  If the question mentions "open", add filter {"status": "Open"}.
- For "show me / list / which tickets" → operation "list".
- "created_at" filters may use ISO format dates ("2024-03-01").
- For relative dates ("this month", "this week", "today"), use the DATASET CONTEXT
  provided in the question — NOT the real-world current date.
  Represent date filters as ">=YYYY-MM-DD" or "<=YYYY-MM-DD" strings.
- If unsure, default to "list" with empty filters.
- Return ONLY the JSON. No explanation, no markdown, no backticks.
"""


# ---------------------------------------------------------------- helpers

def _dataset_context(df: pd.DataFrame) -> str:
    """Build a short text describing the dataset's date range and categories."""
    min_date = df["created_at"].min()
    max_date = df["created_at"].max()
    return (
        f"\nDATASET CONTEXT (use this to resolve relative dates):\n"
        f"- The dataset covers {min_date:%Y-%m-%d} to {max_date:%Y-%m-%d}.\n"
        f"- Treat 'today', 'now', 'this week', and 'this month' as the dataset's "
        f"LATEST date ({max_date:%Y-%m-%d}), NOT the real-world current date.\n"
        f"- 'This month' means {max_date:%Y-%m}. 'Last month' means the month "
        f"before {max_date:%Y-%m}.\n"
        f"- 'This week' means the 7 days ending on {max_date:%Y-%m-%d}.\n"
    )


def _extract_json(text: str) -> dict[str, Any]:
    """LLM sometimes wraps JSON in prose or backticks. Extract it."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in LLM output: {text[:200]}")
    return json.loads(match.group(0))


def plan_query(
    question: str,
    df: pd.DataFrame | None = None,
    max_retries: int = 2,
) -> dict[str, Any]:
    """
    Ask the LLM to convert a question into a structured query plan.
    Injects the dataset's date range so relative dates ("this month") resolve correctly.
    Retries with a correction prompt if the LLM returns invalid JSON.
    """
    context = _dataset_context(df) if df is not None else ""
    full_question = f"{context}\nUSER QUESTION: {question}" if context else question

    correction = ""
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        prompt = full_question if not correction else f"{full_question}\n\n{correction}"
        raw = ask_llm(prompt, system=SYSTEM_PROMPT, temperature=0.0)
        try:
            return _extract_json(raw)
        except (ValueError, json.JSONDecodeError) as e:
            last_error = e
            correction = (
                f"Your previous response was invalid JSON. Error: {e}. "
                f"Return ONLY a valid JSON object matching the schema. "
                f"No prose, no markdown, no backticks."
            )

    raise ValueError(
        f"LLM failed to produce valid JSON after {max_retries + 1} attempts: {last_error}"
    )


# ---------------------------------------------------------------- executor

def _apply_filters(df: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
    for col, val in (filters or {}).items():
        if col not in df.columns:
            continue

        # Date filters with operators (">=2024-03-01", "<=2024-03-15", etc.)
        if col == "created_at" and isinstance(val, str) and val[:2] in (">=", "<=", ">", "<", "=="):
            op = val[:2] if val[:2] in (">=", "<=") else val[0]
            date_str = val[len(op):].strip()
            try:
                target = pd.to_datetime(date_str)
            except Exception:
                continue
            if op == ">=":
                df = df[df["created_at"] >= target]
            elif op == "<=":
                df = df[df["created_at"] <= target]
            elif op == ">":
                df = df[df["created_at"] > target]
            elif op == "<":
                df = df[df["created_at"] < target]
            elif op == "==":
                df = df[df["created_at"].dt.strftime("%Y-%m-%d") == date_str[:10]]
            continue

        # List membership
        if isinstance(val, list):
            df = df[df[col].isin(val)]
            continue

        # Exact date match
        if col == "created_at":
            df = df[df["created_at"].dt.strftime("%Y-%m-%d") == str(val)[:10]]
            continue

        # Default: equality
        df = df[df[col] == val]

    return df


def _humanize_count(n: int, plan: dict) -> str:
    filters = plan.get("filters") or {}
    if filters:
        parts = ", ".join(f"{k}={v}" for k, v in filters.items())
        return f"{n} ticket(s) match [{parts}]."
    return f"{n} ticket(s) in total."


def execute_plan(df: pd.DataFrame, plan: dict[str, Any]) -> str:
    op = (plan.get("operation") or "count").lower()
    df = _apply_filters(df, plan.get("filters") or {})

    if op == "count":
        return _humanize_count(len(df), plan)

    if op in {"avg", "sum", "min", "max"}:
        target = plan.get("target")
        if not target or target not in df.columns:
            return "I couldn't determine which column to aggregate."
        series = pd.to_numeric(df[target], errors="coerce").dropna()
        if series.empty:
            return f"No numeric data available for '{target}'."
        method = {"avg": "mean", "sum": "sum", "min": "min", "max": "max"}[op]
        value = getattr(series, method)()
        return f"{op.upper()} of {target} = {round(float(value), 2)} (over {len(series)} rows)."

    if op == "groupby_count":
        group = plan.get("group_by")
        if not group or group not in df.columns:
            return "I couldn't determine the grouping column."
        counts = df[group].value_counts()
        if counts.empty:
            return "No rows matched your filters."
        sort = plan.get("sort", "desc")
        counts = counts.sort_values(ascending=(sort == "asc"))
        limit = plan.get("limit") or 5
        top = counts.head(limit)
        lines = [f"{idx}: {int(val)}" for idx, val in top.items()]
        return f"Counts by {group}:\n" + "\n".join(lines)

    if op == "groupby_avg":
        group = plan.get("group_by")
        target = plan.get("target")
        if not group or not target:
            return "Need both group_by and target for groupby_avg."
        grouped = df.groupby(group)[target].mean().dropna()
        sort = plan.get("sort", "asc")
        grouped = grouped.sort_values(ascending=(sort == "asc"))
        limit = plan.get("limit") or 5
        top = grouped.head(limit).round(2)
        lines = [f"{idx}: {val}" for idx, val in top.items()]
        return f"Average {target} by {group}:\n" + "\n".join(lines)

    if op == "list":
        limit = plan.get("limit") or 10
        cols = ["ticket_id", "created_at", "priority", "status", "agent_id", "issue_summary"]
        subset = df[cols].head(limit)
        if subset.empty:
            return "No tickets matched your filters."
        return subset.to_string(index=False)

    return f"Unsupported operation: {op}"


# ---------------------------------------------------------------- public API

def answer_question(question: str, df: pd.DataFrame | None = None) -> dict:
    """End-to-end: NL question → plan → answer."""
    if df is None:
        df = load_tickets()
    try:
        plan = plan_query(question, df=df)
        answer = execute_plan(df, plan)
        return {"question": question, "plan": plan, "answer": answer}
    except Exception as e:
        return {"question": question, "plan": None, "answer": f"Error: {e}"}


if __name__ == "__main__":
    samples = [
        "How many tickets are currently open?",
        "Which agent resolved the most tickets?",
        "What is the average customer rating for Technical category tickets?",
        "Show me all Critical tickets that are not resolved.",
        "Which agent resolved the most tickets this month?",
        "Are there any anomalies in resolution times this week?",
    ]
    df = load_tickets()
    for q in samples:
        print("=" * 60)
        print(f"Q: {q}")
        result = answer_question(q, df)
        print(f"Plan: {result['plan']}")
        print(f"A: {result['answer']}\n")