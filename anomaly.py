"""
Anomaly detection over the support tickets DataFrame.

Rules implemented:
  1. Slow resolution       — resolution_time_hrs > SLOW_RESOLUTION_HRS
  2. Stale high-priority   — priority in {High, Critical}, not Resolved, and older than STALE_HOURS
  3. Response time outlier — response_time_hrs > mean + 2 * std

Each rule returns a list of dicts, all combined into one response.
"""

import pandas as pd

from data_loader import load_tickets

SLOW_RESOLUTION_HRS = 48
STALE_HOURS = 24
HIGH_PRIORITIES = {"High", "Critical"}
OUTLIER_Z = 2.0


def _records(df: pd.DataFrame, reason: str) -> list[dict]:
    cols = ["ticket_id", "created_at", "category", "priority", "status",
            "response_time_hrs", "resolution_time_hrs", "agent_id"]
    out = []
    for _, row in df.iterrows():
        rec = {c: (None if pd.isna(row[c]) else row[c]) for c in cols}
        if isinstance(rec["created_at"], pd.Timestamp):
            rec["created_at"] = rec["created_at"].isoformat()
        rec["reason"] = reason
        out.append(rec)
    return out


def detect_slow_resolution(df: pd.DataFrame) -> list[dict]:
    mask = df["resolution_time_hrs"] > SLOW_RESOLUTION_HRS
    return _records(df[mask], f"resolution_time_hrs > {SLOW_RESOLUTION_HRS}h")


def detect_stale_high_priority(df: pd.DataFrame) -> list[dict]:
    # Use the latest ticket timestamp as "now" so results are realistic
    # regardless of when the evaluator runs the system.
    now = df["created_at"].max()
    mask = (
        df["priority"].isin(HIGH_PRIORITIES)
        & (df["status"] != "Resolved")
        & ((now - df["created_at"]).dt.total_seconds() / 3600 > STALE_HOURS)
    )
    return _records(df[mask], "High/Critical unresolved for > 24h (vs dataset snapshot)")


def detect_response_outliers(df: pd.DataFrame) -> list[dict]:
    series = df["response_time_hrs"]
    mean, std = series.mean(), series.std()
    if std == 0 or pd.isna(std):
        return []
    threshold = mean + OUTLIER_Z * std
    mask = series > threshold
    return _records(df[mask], f"response_time_hrs > mean+{OUTLIER_Z}*std ({round(threshold, 2)}h)")


def detect_anomalies(df: pd.DataFrame | None = None) -> dict:
    """Run all anomaly rules and return a structured report."""
    if df is None:
        df = load_tickets()

    slow = detect_slow_resolution(df)
    stale = detect_stale_high_priority(df)
    outliers = detect_response_outliers(df)

    seen = set()
    combined = []
    for rec in slow + stale + outliers:
        key = (rec["ticket_id"], rec["reason"])
        if key not in seen:
            seen.add(key)
            combined.append(rec)

    return {
        "total_anomalies": len(combined),
        "rules": {
            "slow_resolution": {"count": len(slow), "threshold_hrs": SLOW_RESOLUTION_HRS},
            "stale_high_priority": {"count": len(stale), "threshold_hrs": STALE_HOURS},
            "response_time_outlier": {"count": len(outliers), "z_score": OUTLIER_Z},
        },
        "anomalies": combined,
    }


if __name__ == "__main__":
    import json
    report = detect_anomalies()
    print(f"Total anomalies: {report['total_anomalies']}")
    print(json.dumps(report["rules"], indent=2))
    print("\nFirst 5 anomalies:")
    for rec in report["anomalies"][:5]:
        print(f"  {rec['ticket_id']}  {rec['reason']}")