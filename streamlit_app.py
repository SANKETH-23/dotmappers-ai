"""
Modern Streamlit UI for the Support Ticket AI system.
Talks to the FastAPI backend over HTTP.
"""

import requests
import streamlit as st
import pandas as pd

API = "http://127.0.0.1:8080"

# ------------------------------------------------------------------ page config
st.set_page_config(
    page_title="Support Ticket AI",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------ global CSS
st.markdown(
    """
    <style>
    /* ---------- fonts & background ---------- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .stApp {
        background:
            radial-gradient(circle at 0% 0%, rgba(99,102,241,0.08), transparent 45%),
            radial-gradient(circle at 100% 0%, rgba(236,72,153,0.08), transparent 45%),
            #f8fafc;
    }

    /* ---------- hide only the menu and footer, keep header + sidebar toggle ---------- */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stStatusWidget"] {visibility: hidden;}

    /* ---------- hero ---------- */
    .hero {
        padding: 2.5rem 2rem 2rem 2rem;
        border-radius: 20px;
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #db2777 100%);
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 20px 40px -20px rgba(79,70,229,0.5);
    }
    .hero h1 {
        font-size: 2.4rem;
        font-weight: 800;
        margin: 0 0 0.5rem 0;
        letter-spacing: -0.02em;
    }
    .hero p {
        font-size: 1.05rem;
        opacity: 0.92;
        margin: 0;
        font-weight: 400;
    }
    .hero .badge {
        display: inline-block;
        background: rgba(255,255,255,0.18);
        border: 1px solid rgba(255,255,255,0.25);
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-bottom: 0.9rem;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }

    /* ---------- metric cards ---------- */
    .metric-row {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: white;
        border-radius: 16px;
        padding: 1.25rem 1.25rem 1.1rem 1.25rem;
        border: 1px solid #e5e7eb;
        box-shadow: 0 4px 12px -6px rgba(0,0,0,0.06);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 24px -10px rgba(79,70,229,0.25);
    }
    .metric-card .label {
        font-size: 0.72rem;
        font-weight: 600;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 0.4rem;
    }
    .metric-card .value {
        font-size: 1.8rem;
        font-weight: 800;
        color: #111827;
        line-height: 1.1;
    }
    .metric-card .sub {
        font-size: 0.78rem;
        color: #9ca3af;
        margin-top: 0.3rem;
    }

    /* ---------- section headers ---------- */
    .section-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #111827;
        margin: 1.5rem 0 0.75rem 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    /* ---------- example chips ---------- */
    .chip {
        display: inline-block;
        background: #eef2ff;
        color: #4338ca;
        padding: 6px 14px;
        border-radius: 999px;
        font-size: 0.82rem;
        font-weight: 500;
        margin: 3px 5px 3px 0;
        border: 1px solid #e0e7ff;
    }

    /* ---------- answer card ---------- */
    .answer-card {
        background: linear-gradient(135deg, #ecfdf5 0%, #f0fdf4 100%);
        border: 1px solid #a7f3d0;
        border-left: 4px solid #10b981;
        border-radius: 14px;
        padding: 1.25rem 1.5rem;
        margin-top: 1rem;
        font-size: 1.02rem;
        color: #065f46;
        line-height: 1.6;
    }
    .answer-card strong { color: #064e3b; }

    /* ---------- plan card ---------- */
    .plan-card {
        background: #f9fafb;
        border: 1px dashed #d1d5db;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        font-family: 'JetBrains Mono', ui-monospace, monospace;
        font-size: 0.82rem;
        color: #374151;
    }

    /* ---------- anomaly reason ---------- */
    .reason-pill {
        display: inline-block;
        background: #fef3c7;
        color: #92400e;
        padding: 2px 10px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 600;
        border: 1px solid #fde68a;
    }

    /* ---------- buttons ---------- */
    .stButton > button {
        background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 0.55rem 1.4rem !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        box-shadow: 0 4px 14px -4px rgba(79,70,229,0.5) !important;
        transition: all 0.15s ease !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 8px 20px -6px rgba(79,70,229,0.6) !important;
    }

    /* ---------- text input ---------- */
    .stTextInput > div > div > input {
        border-radius: 10px !important;
        border: 1px solid #e5e7eb !important;
        padding: 0.7rem 1rem !important;
        font-size: 0.95rem !important;
        background: white !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #7c3aed !important;
        box-shadow: 0 0 0 3px rgba(124,58,237,0.15) !important;
    }

    /* ---------- tabs ---------- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: transparent;
        border-bottom: 1px solid #e5e7eb;
    }
    .stTabs [data-baseweb="tab"] {
        height: 44px;
        border-radius: 10px 10px 0 0;
        padding: 0 20px;
        font-weight: 600;
        color: #6b7280;
        background: transparent;
        border: none;
    }
    .stTabs [aria-selected="true"] {
        color: #4f46e5 !important;
        background: white !important;
        border-bottom: 2px solid #4f46e5 !important;
    }

    /* ---------- dataframes ---------- */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #e5e7eb;
    }

    /* ---------- sidebar ---------- */
    section[data-testid="stSidebar"] {
        background: white;
        border-right: 1px solid #e5e7eb;
    }
    section[data-testid="stSidebar"] .status-dot {
        display: inline-block;
        width: 8px; height: 8px;
        border-radius: 50%;
        background: #10b981;
        margin-right: 6px;
        box-shadow: 0 0 0 3px rgba(16,185,129,0.2);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------ hero
st.markdown(
    """
    <div class="hero">
        <span class="badge">● Live</span>
        <h1>🎫 Support Ticket AI</h1>
        <p>Ask questions in plain English, detect anomalies, and explore 500 support tickets — powered by an LLM.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------ sidebar: health
with st.sidebar:
    st.markdown("### ⚙️ System Status")

    health_ok = False
    info = {}
    try:
        r = requests.get(f"{API}/health", timeout=5)
        if r.ok:
            info = r.json()
            health_ok = True
    except Exception:
        pass

    if health_ok:
        st.markdown(
            '<p><span class="status-dot"></span><strong>API online</strong></p>',
            unsafe_allow_html=True,
        )
        st.metric("Tickets loaded", info.get("rows", "—"))
        st.metric("Columns", len(info.get("columns", [])))
    else:
        st.error("API offline")
        st.caption("Start the backend with:")
        st.code("uvicorn main:app --reload --port 8080", language="bash")

    st.divider()
    st.markdown("### ℹ️ About")
    st.caption(
        "Built with FastAPI, Streamlit, pandas, and a Groq-hosted LLM "
        "(with local Ollama fallback)."
    )
    st.caption(f"Backend: `{API}`")

# ------------------------------------------------------------------ tabs
tab_query, tab_anomalies, tab_browse = st.tabs(
    ["🔎  Ask a question", "⚠️  Anomalies", "📋  Browse tickets"]
)

# ================================================================== Tab 1
with tab_query:
    st.markdown('<div class="section-title">💬 Ask a question about the tickets</div>', unsafe_allow_html=True)

    examples = [
        "How many tickets are currently open?",
        "Which agent resolved the most tickets?",
        "What is the average customer rating for Technical tickets?",
        "Show me all Critical tickets not resolved.",
    ]
    st.markdown(
        "**Try one:** &nbsp;"
        + " ".join(f'<span class="chip">{ex}</span>' for ex in examples),
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([5, 1])
    with col1:
        question = st.text_input(
            "Your question",
            placeholder="e.g. How many critical tickets are unresolved?",
            label_visibility="collapsed",
        )
    with col2:
        ask_clicked = st.button("Ask ✨", width="stretch", type="primary")

    # Example chips → set question via session state
    for ex in examples:
        if st.button(ex, key=f"chip_{ex}", help="Click to run this question"):
            question = ex
            ask_clicked = True

    if ask_clicked and question.strip():
        with st.spinner("Thinking…"):
            try:
                r = requests.get(f"{API}/query", params={"q": question}, timeout=60)
                if r.ok:
                    data = r.json()
                    st.markdown(
                        f'<div class="answer-card">✅ <strong>Answer:</strong><br>{data["answer"]}</div>',
                        unsafe_allow_html=True,
                    )
                    with st.expander("🔍 Query plan (generated by LLM)"):
                        st.json(data["plan"])
                else:
                    st.error(f"API error {r.status_code}: {r.text}")
            except Exception as e:
                st.error(f"Request failed: {e}")
    elif ask_clicked:
        st.warning("Please type a question first.")

# ================================================================== Tab 2
with tab_anomalies:
    st.markdown('<div class="section-title">⚠️ Anomaly detection</div>', unsafe_allow_html=True)
    st.caption(
        "Scans every ticket against three rules: slow resolution (>48h), "
        "stale high-priority tickets (>24h unresolved), and response-time outliers (>2σ)."
    )

    if st.button("Run detection", type="primary"):
        with st.spinner("Scanning tickets…"):
            try:
                r = requests.get(f"{API}/anomalies", timeout=60)
                if r.ok:
                    data = r.json()
                    rules = data["rules"]

                    st.markdown(
                        f"""
                        <div class="metric-row">
                            <div class="metric-card">
                                <div class="label">Total anomalies</div>
                                <div class="value">{data['total_anomalies']}</div>
                                <div class="sub">flagged tickets</div>
                            </div>
                            <div class="metric-card">
                                <div class="label">Slow resolution</div>
                                <div class="value">{rules['slow_resolution']['count']}</div>
                                <div class="sub">&gt; {rules['slow_resolution']['threshold_hrs']}h</div>
                            </div>
                            <div class="metric-card">
                                <div class="label">Stale high-priority</div>
                                <div class="value">{rules['stale_high_priority']['count']}</div>
                                <div class="sub">&gt; {rules['stale_high_priority']['threshold_hrs']}h unresolved</div>
                            </div>
                            <div class="metric-card">
                                <div class="label">Response outliers</div>
                                <div class="value">{rules['response_time_outlier']['count']}</div>
                                <div class="sub">&gt; mean + {rules['response_time_outlier']['z_score']}σ</div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    if data["anomalies"]:
                        df = pd.DataFrame(data["anomalies"])
                        preferred = ["ticket_id", "created_at", "priority", "status",
                                     "agent_id", "reason", "response_time_hrs", "resolution_time_hrs"]
                        cols = [c for c in preferred if c in df.columns] + \
                               [c for c in df.columns if c not in preferred]
                        df = df[cols]

                        st.markdown('<div class="section-title">📌 Flagged tickets</div>', unsafe_allow_html=True)
                        st.dataframe(df, width="stretch", height=420)
                    else:
                        st.success("No anomalies detected.")
                else:
                    st.error(f"API error {r.status_code}")
            except Exception as e:
                st.error(f"Request failed: {e}")

# ================================================================== Tab 3
with tab_browse:
    st.markdown('<div class="section-title">📋 Browse raw tickets</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    status = c1.selectbox("Status", ["Any", "Open", "Resolved", "Escalated"])
    priority = c2.selectbox("Priority", ["Any", "Low", "Medium", "High", "Critical"])
    category = c3.selectbox("Category", ["Any", "Billing", "Technical", "General"])
    limit = c4.slider("Rows", 5, 200, 25, step=5)

    params = {"limit": limit}
    if status != "Any":
        params["status"] = status
    if priority != "Any":
        params["priority"] = priority
    if category != "Any":
        params["category"] = category

    try:
        r = requests.get(f"{API}/tickets", params=params, timeout=30)
        if r.ok:
            data = r.json()
            st.caption(f"Showing **{data['count']}** ticket(s)")
            st.dataframe(pd.DataFrame(data["tickets"]), width="stretch", height=500)
        else:
            st.error(f"API error {r.status_code}")
    except Exception as e:
        st.error(f"Request failed: {e}")