"""
End-to-end smoke tests for the Support Ticket AI system.
Run with: python test_system.py
"""

import sys
import requests

API = "http://127.0.0.1:8080"
PASS = "[PASS]"
FAIL = "[FAIL]"


def check(name: str, condition: bool, detail: str = "") -> bool:
    if condition:
        print(f"{PASS} {name}")
        return True
    print(f"{FAIL} {name}  --  {detail}")
    return False


def main() -> int:
    failures = 0
    print("=" * 60)
    print(" Support Ticket AI - System Tests")
    print("=" * 60)

    # 1. HEALTH
    print("\n--- 1. Health check ---")
    try:
        r = requests.get(f"{API}/health", timeout=10)
        body = r.json() if r.ok else {}
        failures += not check("Status 200", r.ok, str(r.status_code))
        failures += not check("Rows == 500", body.get("rows") == 500, str(body.get("rows")))
        failures += not check("Has columns", len(body.get("columns", [])) == 10)
    except Exception as e:
        print(f"{FAIL} /health crashed: {e}")
        failures += 1

    # 2. NL QUERIES
    print("\n--- 2. Natural language queries ---")
    test_cases = [
        ("How many tickets are currently open?", ["111", "open"]),
        ("Which agent resolved the most tickets?", ["agent", "AGT"]),
        ("What is the average customer rating for Technical tickets?", ["3.7", "avg", "average"]),
        ("Show me all Critical tickets not resolved.", ["ticket", "critical"]),
        ("Show me all Critical tickets not resolved within 12 hours.", ["ticket", "critical"]),
        ("How many tickets in total?", ["500"]),
        ("What is the average resolution time?", ["avg", "average", "resolution"]),
        ("Show me all Open Billing tickets.", ["ticket"]),
    ]
    for q, expected_keywords in test_cases:
        try:
            r = requests.get(f"{API}/query", params={"q": q}, timeout=60)
            if not r.ok:
                print(f"{FAIL} Q: '{q}' -> HTTP {r.status_code}")
                failures += 1
                continue
            data = r.json()
            answer = (data.get("answer") or "").lower()
            ok = any(kw.lower() in answer for kw in expected_keywords)
            failures += not check(f"Q: '{q}'", ok, f"answer={answer[:80]}")
        except Exception as e:
            print(f"{FAIL} Q: '{q}' crashed: {e}")
            failures += 1

    # 3. STRUCTURED DATA
    print("\n--- 3. Structured data in responses ---")
    try:
        r = requests.get(f"{API}/query",
                         params={"q": "Show me all Critical tickets not resolved."},
                         timeout=60)
        data = r.json()
        failures += not check("Response has 'data' field", "data" in data)
        failures += not check("'data' is a list", isinstance(data.get("data"), list))
        failures += not check("'columns' present", isinstance(data.get("columns"), list))
        if data.get("data"):
            first = data["data"][0]
            failures += not check("Row has ticket_id", "ticket_id" in first)
    except Exception as e:
        print(f"{FAIL} Structured data test crashed: {e}")
        failures += 1

    # 4. ANOMALIES
    print("\n--- 4. Anomaly detection ---")
    try:
        r = requests.get(f"{API}/anomalies", timeout=60)
        body = r.json() if r.ok else {}
        failures += not check("Status 200", r.ok)
        failures += not check("Has total_anomalies", "total_anomalies" in body)
        failures += not check("Has rules", "rules" in body)
        failures += not check("Has slow_resolution", "slow_resolution" in body.get("rules", {}))
        failures += not check("Has stale_high_priority", "stale_high_priority" in body.get("rules", {}))
        failures += not check("Has response_time_outlier", "response_time_outlier" in body.get("rules", {}))
        failures += not check("Anomalies is a list", isinstance(body.get("anomalies"), list))
    except Exception as e:
        print(f"{FAIL} /anomalies crashed: {e}")
        failures += 1

    # 5. TICKETS ENDPOINT
    print("\n--- 5. /tickets endpoint ---")
    try:
        r = requests.get(f"{API}/tickets", params={"limit": 5}, timeout=30)
        body = r.json() if r.ok else {}
        failures += not check("Status 200", r.ok)
        failures += not check("Returns <= 5 tickets", body.get("count", 99) <= 5)
        failures += not check("No NaN in JSON", b"NaN" not in r.content)
    except Exception as e:
        print(f"{FAIL} /tickets crashed: {e}")
        failures += 1

    # 6. EDGE CASES
    print("\n--- 6. Edge cases (must NOT crash 500) ---")
    edge_cases = [
        "weather today",
        "xyzzy",
        "average",
        "which agent",
        "show me everything",
    ]
    for q in edge_cases:
        try:
            r = requests.get(f"{API}/query", params={"q": q}, timeout=60)
            ok = r.status_code in (200, 422)
            failures += not check(f"Edge: '{q}'", ok, f"HTTP {r.status_code}")
        except Exception as e:
            print(f"{FAIL} Edge case '{q}' crashed: {e}")
            failures += 1

    # 7. BAD INPUT
    print("\n--- 7. Bad input handling ---")
    try:
        r = requests.get(f"{API}/query", params={"q": ""}, timeout=10)
        failures += not check("Empty query rejected (422)", r.status_code == 422)
    except Exception as e:
        print(f"{FAIL} Empty query test crashed: {e}")
        failures += 1

    # SUMMARY
    print("\n" + "=" * 60)
    if failures == 0:
        print(f" {PASS} ALL TESTS PASSED")
    else:
        print(f" {FAIL} {failures} test(s) failed")
    print("=" * 60)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())