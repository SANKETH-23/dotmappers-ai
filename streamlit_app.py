"""
Minimal Streamlit UI for the Support Ticket AI system.
Talks to the FastAPI backend over HTTP.
"""

import requests
import streamlit as st
import pandas as pd

API = "http://127.0.0.1:8080"

st.set_page_config(page_title="Support Ticket AI", page_icon="🎫", layout="wide")
st.title("🎫 Support Ticket AI")
st.caption("Natural language querying + anomaly detection over 500 support tickets.")

# ---------------------------------------------------------------- sidebar: health
with st.sidebar:
    st.header("System Status")
    try:
        r = requests.get(f"{API}/health", timeout=5)
        if r.ok:
            info = r.json()
            st.success("API online")
            st.metric("Rows", info["rows"])
            st.metric("Columns", len(info["columns"]))
        else:
            st.error(f"API error: {r.status_code}")
    except Exception as e:
        st.error(f"Cannot reach API: {e}")
    st.caption(f"Backend: {API}")

# ---------------------------------------------------------------- tabs
tab_query, tab_anomalies, tab_browse = st.tabs(["🔎 Ask a question", "⚠️ Anomalies", "📋 Browse tickets"])

# ---------------------------------------------------------------- Tab 1: NL query
with tab_query:
    st.subheader("Ask a question about the tickets")
    st.write("Examples:")
    examples = [
        "How many tickets are currently open?",
        "Which agent resolved the most tickets?",
        "What is the average customer rating for Technical category tickets?",
        "Show me all Critical tickets not resolved within 12 hours.",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex}"):
            st.session_state["question"] = ex

    question = st.text_input("Your question", value=st.session_state.get("question", ""))

    if st.button("Ask", type="primary"):
        if not question.strip():
            st.warning("Type a question first.")
        else:
            with st.spinner("Thinking..."):
                try:
                    r = requests.get(f"{API}/query", params={"q": question}, timeout=60)
                    if r.ok:
                        data = r.json()
                        st.markdown("### Answer")
                        st.success(data["answer"])
                        with st.expander("Query plan (from LLM)"):
                            st.json(data["plan"])
                    else:
                        st.error(f"API error {r.status_code}: {r.text}")
                except Exception as e:
                    st.error(f"Request failed: {e}")

# ---------------------------------------------------------------- Tab 2: anomalies
with tab_anomalies:
    st.subheader("Anomaly report")
    if st.button("Run detection", type="primary"):
        with st.spinner("Scanning tickets..."):
            try:
                r = requests.get(f"{API}/anomalies", timeout=60)
                if r.ok:
                    data = r.json()
                    st.metric("Total anomalies", data["total_anomalies"])

                    cols = st.columns(3)
                    cols[0].metric("Slow resolution", data["rules"]["slow_resolution"]["count"])
                    cols[1].metric("Stale high-priority", data["rules"]["stale_high_priority"]["count"])
                    cols[2].metric("Response outliers", data["rules"]["response_time_outlier"]["count"])

                    if data["anomalies"]:
                        df = pd.DataFrame(data["anomalies"])
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("No anomalies detected.")
                else:
                    st.error(f"API error {r.status_code}")
            except Exception as e:
                st.error(f"Request failed: {e}")

# ---------------------------------------------------------------- Tab 3: browse
with tab_browse:
    st.subheader("Browse raw tickets")
    c1, c2, c3 = st.columns(3)
    status = c1.selectbox("Status", ["", "Open", "Resolved", "Escalated"])
    priority = c2.selectbox("Priority", ["", "Low", "Medium", "High", "Critical"])
    category = c3.selectbox("Category", ["", "Billing", "Technical", "General"])
    limit = st.slider("Rows", 5, 100, 20)

    params = {"limit": limit}
    if status:
        params["status"] = status
    if priority:
        params["priority"] = priority
    if category:
        params["category"] = category

    try:
        r = requests.get(f"{API}/tickets", params=params, timeout=30)
        if r.ok:
            data = r.json()
            st.caption(f"Showing {data['count']} tickets")
            st.dataframe(pd.DataFrame(data["tickets"]), use_container_width=True)
        else:
            st.error(f"API error {r.status_code}")
    except Exception as e:
        st.error(f"Request failed: {e}")