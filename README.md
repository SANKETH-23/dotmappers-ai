# Support Ticket AI

An AI-powered assistant for customer support tickets. Ask questions in plain English, detect anomalies, and browse tickets — all through a REST API and a Streamlit UI.

Built for the **DOTMappers AI Engineer Assessment**.

---

## What it does

1. **Ingests** `support_tickets.csv` (500 rows) into a pandas DataFrame.
2. **Answers natural language questions** like *"How many critical tickets are unresolved?"* using an LLM that converts them into structured queries.
3. **Detects anomalies** such as slow resolutions, stale high-priority tickets, and response-time outliers.
4. **Exposes everything** via a FastAPI REST API and a Streamlit UI.

---

## Architecture

```
┌──────────────┐      HTTP      ┌──────────────┐
│  Streamlit   │ ─────────────► │   FastAPI    │
│     UI       │                │   (main.py)  │
└──────────────┘                └──────┬───────┘
                                       │
                       ┌───────────────┼───────────────┐
                       │               │               │
                       ▼               ▼               ▼
                ┌────────────┐  ┌────────────┐  ┌────────────┐
                │  query_    │  │  anomaly   │  │  data_     │
                │  engine.py │  │    .py     │  │  loader.py │
                └─────┬──────┘  └────────────┘  └────────────┘
                      │
                      ▼
                ┌────────────┐
                │   llm.py   │───► Groq API (free tier)
                └────────────┘    or local Ollama fallback
```

### Component choices

| Component | Why |
|---|---|
| **pandas** | Fast enough for 500 rows; simple to query and easy to explain |
| **FastAPI** | Async-native (important for LLM latency), auto-generated `/docs`, Pydantic validation |
| **Streamlit** | Python-only UI, minimal setup, ideal for data apps |
| **Groq (llama-3.1-8b-instant / gpt-oss-20b)** | Free tier, extremely fast, zero cost, no local GPU required |
| **Ollama fallback** | Offline option if `GROQ_API_KEY` isn't set |

### Why the LLM outputs JSON, not pandas code

The LLM only produces a **small query spec**:

```json
{
  "operation": "count",
  "filters": {"status": "Open", "priority": "Critical"},
  "group_by": null,
  "sort": null,
  "limit": null
}
```

Python then applies that spec to the DataFrame. This is safer (no prompt injection into executable code), more deterministic, and easier to debug.

---

## Setup

### 1. Clone and enter the project

```bash
git clone <your-repo-url>
cd dotmappers-ai
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Get a free Groq API key

1. Visit https://console.groq.com/keys
2. Sign up (free, no card)
3. Create an API key
4. Create a `.env` file in the project root:

```
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama-3.1-8b-instant
```

> **No Groq key?** The system falls back to a local Ollama server automatically. Just run `ollama serve` and `ollama pull llama3.2:1b`.

### 5. Add the dataset

Place `support_tickets.csv` in the project root. A sample generator is included as `generate_data.py` if you need one.

---

## Running the system

### Terminal 1 — start the API

```bash
uvicorn main:app --reload --port 8080
```

- API root: http://127.0.0.1:8080
- Interactive docs: http://127.0.0.1:8080/docs

### Terminal 2 — start the UI

```bash
streamlit run streamlit_app.py
```

- UI opens at http://localhost:8501

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe + dataset stats |
| GET | `/query?q=...` | Natural-language question |
| GET | `/anomalies` | Full anomaly report |
| GET | `/tickets?status=&priority=&category=&limit=` | Browse raw tickets |

### Example: `/query`

```bash
curl "http://127.0.0.1:8080/query?q=How many open tickets are there"
```

Response:
```json
{
  "question": "How many open tickets are there",
  "plan": {"operation": "count", "filters": {"status": "Open"}},
  "answer": "111 ticket(s) match [status=Open]."
}
```

### Example: `/anomalies`

```bash
curl "http://127.0.0.1:8080/anomalies"
```

Response (truncated):
```json
{
  "total_anomalies": 101,
  "rules": {
    "slow_resolution": {"count": 21, "threshold_hrs": 48},
    "stale_high_priority": {"count": 80, "threshold_hrs": 24},
    "response_time_outlier": {"count": 0, "z_score": 2.0}
  },
  "anomalies": [ ... ]
}
```

---

## Example queries & outputs

| Question | Answer |
|---|---|
| How many tickets are currently open? | `111 ticket(s) match [status=Open].` |
| Which agent resolved the most tickets? | `AGT-09: 37` (also `AGT-12: 37`) |
| What is the average customer rating for Technical tickets? | `AVG of cust_rating = 3.74 (over 104 rows).` |
| Show me all Critical tickets not resolved. | Table of 10 Critical Open/Escalated tickets |

---

## Anomaly rules

| Rule | Definition |
|---|---|
| **Slow resolution** | `resolution_time_hrs > 48` |
| **Stale high-priority** | priority in {High, Critical}, not Resolved, and older than 24h relative to the dataset's latest ticket |
| **Response time outlier** | `response_time_hrs > mean + 2 * std` |

The "stale" rule uses the dataset's max `created_at` as the reference "now" so results are stable regardless of when the evaluator runs the system.

---

## Known limitations

- **LLM output is not always valid JSON.** The system extracts JSON from prose/backticks and fails gracefully. A retry loop would improve robustness.
- **No pagination on `/tickets`** beyond a `limit` parameter.
- **No authentication** on the API — intended for local/demo use.
- **Anomaly thresholds are hardcoded.** They could be made configurable via environment variables.
- **`created_at` filters** only support exact date matching, not ranges.
- **Single-process cache** for the DataFrame (`lru_cache`). Fine for 500 rows; would need Redis or similar at scale.

---

## What I would improve with more time

1. **Swap pandas for DuckDB** — better analytical query performance and native SQL.
2. **Add a retry-with-correction loop** around the LLM planner.
3. **Move LLM calls to async** (`httpx.AsyncClient`) to fully leverage FastAPI's concurrency.
4. **Add tests** with `pytest` and `httpx` for endpoint coverage.
5. **Docker Compose** for one-command startup (`docker-compose up`).
6. **Configurable thresholds** in `.env`.

---

## License

This project was created for an assessment and is provided as-is.