"""
Natural Language → structured query → DataFrame answer.

Design: the LLM only outputs a small JSON spec (operation, filters, group_by, sort, limit).
Python then applies it to the DataFrame. The LLM never touches raw pandas code.

Returns both a human-readable text answer AND optional structured data
(for rendering tables in the UI/API).
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
- For "show me / list / which tickets" → operation "list".

NEGATION AND SLA RULES (very important):
- "not resolved" means status is NOT "Resolved". Use filter {"status": ["Open", "Escalated"]}.
- "unresolved" / "still open" / "not yet resolved" → status in ["Open", "Escalated"].
- "not resolved within N hours" is NOT a status filter by itself. It means:
    status in ["Open", "Escalated"]  (unresolved tickets)
    AND they are older than N hours relative to the dataset's latest timestamp.
  Represent as: filters {"status": ["Open", "Escalated"]}.
- "resolved within N hours" (WITHOUT "not") → status = "Resolved" AND resolution_time_hrs <= N.
- Do NOT add {"status": "Resolved"} when the question contains "not resolved" or "unresolved".

RELATIVE DATES:
- For "this month", "this week", "today", use the DATASET CONTEXT — NOT the real-world date.
- Represent date filters as ">=YYYY-MM-DD" or "<=YYYY-MM-DD" strings.

- If unsure, default to "list" with empty filters.
- Return ONLY the JSON. No explanation, no markdown, no backticks.
"""


# ---------------------------------------------------------------- helpers

def _dataset_context(df: pd.DataFrame) -> str:
    """Build a short text describing the dataset's date range."""
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


def _fix_negation(question: str, plan: dict) -> dict:
    """
    Post-process the LLM plan to catch common negation mistakes.
    The small LLM often drops 'not' from 'not resolved'.
    """
    q = question.lower()
    filters = plan.get("filters") or {}

    has_negation = ("not resolved" in q or "unresolved" in q or "not yet resolved" in q)
    if has_negation and filters.get("status") == "Resolved":
        filters["status"] = ["Open", "Escalated"]

    plan["filters"] = filters
    return plan


def plan_query(
    question: str,
    df: pd.DataFrame | None = None,
    max_retries: int = 2,
) -> dict[str, Any]:
    """
    Ask the LLM to convert a question into a structured query plan.
    Injects the dataset's date range so relative dates resolve correctly.
    Retries with a correction prompt if the LLM returns invalid JSON.
    Post-processes to catch negation mistakes.
    """
    context = _dataset_context(df) if df is not None else ""
    full_question = f"{context}\nUSER QUESTION: {question}" if context else question

    correction = ""
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        prompt = full_question if not correction else f"{full_question}\n\n{correction}"
        raw = ask_llm(prompt, system=SYSTEM_PROMPT, temperature=0.0)
        try:
            plan = _extract_json(raw)
            return _fix_negation(question, plan)
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

        # Date filters with operators
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


def _humanize_filters(filters: dict) -> str:
    if not filters:
        return ""
    parts = []
    for k, v in filters.items():
        if isinstance(v, list):
            parts.append(f"{k} in {v}")
        else:
            parts.append(f"{k} = {v}")
    return ", ".join(parts)


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to a list of JSON-safe records."""
    records = []
    for _, row in df.iterrows():
        rec = {}
        for col in df.columns:
            val = row[col]
            if pd.isna(val):
                rec[col] = None
            elif isinstance(val, pd.Timestamp):
                rec[col] = val.strftime("%Y-%m-%d %H:%M")
            else:
                rec[col] = val
        records.append(rec)
    return records


def execute_plan(df: pd.DataFrame, plan: dict[str, Any]) -> dict:
    """
    Apply a query plan to the DataFrame.
    Returns a dict with keys: answer (str), data (list|None), columns (list|None).
    """
    op = (plan.get("operation") or "count").lower()
    filtered = _apply_filters(df, plan.get("filters") or {})
    filters_str = _humanize_filters(plan.get("filters") or {})

    # ---------------------------------------------------------- count
    if op == "count":
        n = len(filtered)
        if filters_str:
            return {"answer": f"**{n} ticket(s)** match [{filters_str}].", "data": None, "columns": None}
        return {"answer": f"**{n} ticket(s)** in total.", "data": None, "columns": None}

    # ---------------------------------------------------------- scalar aggregation
    if op in {"avg", "sum", "min", "max"}:
        target = plan.get("target")
        if not target or target not in filtered.columns:
            return {"answer": "I couldn't determine which column to aggregate.", "data": None, "columns": None}
        series = pd.to_numeric(filtered[target], errors="coerce").dropna()
        if series.empty:
            return {"answer": f"No numeric data available for '{target}'.", "data": None, "columns": None}
        method = {"avg": "mean", "sum": "sum", "min": "min", "max": "max"}[op]
        value = getattr(series, method)()
        label = {"avg": "Average", "sum": "Sum", "min": "Min", "max": "Max"}[op]
        answer = f"**{label} of {target}** = `{round(float(value), 2)}`  \n_(over {len(series)} rows)_"
        if filters_str:
            answer += f"  \n_Filters: {filters_str}_"
        return {"answer": answer, "data": None, "columns": None}

    # ---------------------------------------------------------- groupby count
    if op == "groupby_count":
        group = plan.get("group_by")
        if not group or group not in filtered.columns:
            return {"answer": "I couldn't determine the grouping column.", "data": None, "columns": None}
        counts = filtered[group].value_counts()
        if counts.empty:
            return {"answer": "No rows matched your filters.", "data": None, "columns": None}
        sort = plan.get("sort", "desc")
        counts = counts.sort_values(ascending=(sort == "asc"))
        limit = plan.get("limit") or 10
        top = counts.head(limit)
        records = [{group: str(idx), "count": int(val)} for idx, val in top.items()]
        answer = f"**Top {len(records)} by `{group}`:**"
        if filters_str:
            answer += f"  \n_Filters: {filters_str}_"
        return {"answer": answer, "data": records, "columns": [group, "count"]}

    # ---------------------------------------------------------- groupby avg
    if op == "groupby_avg":
        group = plan.get("group_by")
        target = plan.get("target")
        if not group or not target:
            return {"answer": "Need both group_by and target for groupby_avg.", "data": None, "columns": None}
        if group not in filtered.columns or target not in filtered.columns:
            return {"answer": "Column not found for groupby_avg.", "data": None, "columns": None}
        grouped = filtered.groupby(group)[target].mean().dropna()
        sort = plan.get("sort", "asc")
        grouped = grouped.sort_values(ascending=(sort == "asc"))
        limit = plan.get("limit") or 10
        top = grouped.head(limit).round(2)
        records = [{group: str(idx), f"avg_{target}": float(val)} for idx, val in top.items()]
        answer = f"**Average `{target}` by `{group}`:**"
        if filters_str:
            answer += f"  \n_Filters: {filters_str}_"
        return {"answer": answer, "data": records, "columns": [group, f"avg_{target}"]}

    # ---------------------------------------------------------- list
    if op == "list":
        limit = plan.get("limit") or 20
        cols = ["ticket_id", "created_at", "category", "priority", "status",
                "agent_id", "cust_rating", "issue_summary"]
        cols = [c for c in cols if c in filtered.columns]
        subset = filtered[cols].head(limit)
        if subset.empty:
            return {"answer": "No tickets matched your filters.", "data": None, "columns": None}
        records = _df_to_records(subset)
        total = len(filtered)
        shown = len(records)
        answer = f"**{total} ticket(s) matched**"
        if shown < total:
            answer += f" — showing first {shown}"
        if filters_str:
            answer += f"  \n_Filters: {filters_str}_"
        return {"answer": answer, "data": records, "columns": cols}

    return {"answer": f"Unsupported operation: {op}", "data": None, "columns": None}


# ---------------------------------------------------------------- public API

def answer_question(question: str, df: pd.DataFrame | None = None) -> dict:
    """End-to-end: NL question → plan → answer + optional structured data."""
    if df is None:
        df = load_tickets()
    try:
        plan = plan_query(question, df=df)
        result = execute_plan(df, plan)
        return {
            "question": question,
            "plan": plan,
            "answer": result["answer"],
            "data": result.get("data"),
            "columns": result.get("columns"),
        }
    except Exception as e:
        return {
            "question": question,
            "plan": None,
            "answer": f"Error: {e}",
            "data": None,
            "columns": None,
        }


if __name__ == "__main__":
    samples = [
        "How many tickets are currently open?",
        "Which agent resolved the most tickets?",
        "What is the average customer rating for Technical category tickets?",
        "Show me all Critical tickets that are not resolved.",
        "Show me all Critical tickets not resolved within 12 hours.",
    ]
    df = load_tickets()
    for q in samples:
        print("=" * 60)
        print(f"Q: {q}")
        result = answer_question(q, df)
        print(f"Plan: {result['plan']}")
        print(f"A: {result['answer']}")
        if result["data"]:
            print(f"Data rows: {len(result['data'])}")
        print()