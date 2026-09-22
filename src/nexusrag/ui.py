import json
import os
from pathlib import Path

import httpx
import streamlit as st

API = os.getenv("API_BASE_URL", "http://127.0.0.1:58000")
EXAMPLES = [
    "What is Checkout responsible for?",
    "Which data store does Cart use?",
    "How does Checkout reach Quote through Shipping?",
    "What messaging path connects Checkout to Accounting?",
    "Which direct service-call targets do Frontend and Checkout share?",
    "Will a Kafka outage definitely fail every checkout?",
]
st.set_page_config(page_title="NexusRAG", page_icon="🔎", layout="wide")
st.title("NexusRAG")
st.caption("Comparing Vector and Knowledge-Graph Retrieval for Architecture Documentation")
st.sidebar.caption("LOCAL EXPERIMENT · ASTRONOMY SHOP")
view = st.sidebar.radio("View", ["Ask / Compare", "Evidence and execution", "Benchmark results"])
try:
    ready = httpx.get(f"{API}/ready", timeout=6)
    if ready.is_success:
        st.sidebar.success("Corpus ready")
        if ready.json().get("graph_source") == "mermaid_fixture":
            st.sidebar.info(
                "Diagnostic graph fixture · LLM extraction has not run for this corpus."
            )
        if not ready.json().get("generation_configured"):
            st.sidebar.warning(
                "Generation disabled: configure OPENAI_API_KEY and DISABLE_PAID_API=false for the live experiment."
            )
    else:
        st.sidebar.warning("Corpus not ready. Run ingestion from the README.")
except httpx.HTTPError:
    st.sidebar.warning("API unavailable. Start the local Compose stack.")


def render(result):
    if result.get("status") == "failed":
        st.error(result.get("error", "Query failed"))
        return
    answer = result.get("answer")
    evidence = {c["chunk_id"]: c for c in result["evidence"]}
    if answer:
        st.caption(answer["status"].replace("_", " ").upper())
        for statement in answer["statements"]:
            st.write(statement["text"])
            for id_ in statement["evidence_ids"]:
                chunk = evidence[id_]
                st.markdown(
                    f"[{chunk['title']} · lines {chunk['line_start']}–{chunk['line_end']}]"
                    f"({chunk['source_url']}#L{chunk['line_start']}-L{chunk['line_end']})"
                )
        for limitation in answer["limitations"]:
            st.info(limitation)
    trace = result["trace"]
    cols = st.columns(3)
    cols[0].metric("Total", f"{trace['latency_ms']['total'] / 1000:.2f} s")
    cols[1].metric("Estimated API cost", f"${trace['estimated_cost_usd']:.5f}")
    cols[2].metric(
        "Tokens",
        sum((c.get("input_tokens") or 0) + (c.get("output_tokens") or 0) for c in trace["calls"]),
    )
    if trace["fallbacks"]:
        st.warning("Retrieval notes: " + ", ".join(trace["fallbacks"]))
    for path in result["paths"]:
        with st.expander("Path: " + " → ".join(path["nodes"])):
            for edge in path["assertions"]:
                st.code(f"{edge['subject']} —{edge['predicate']}→ {edge['object']}")
                for support in edge["evidence"]:
                    st.text(support["quote"])
    with st.expander("Retrieved source passages"):
        for chunk in evidence.values():
            st.markdown(f"**{chunk['title']} · {chunk['section']}**")
            st.caption(f"Lines {chunk['line_start']}–{chunk['line_end']} · {chunk['chunk_id']}")
            st.code(chunk["text"], language="markdown")
    with st.expander("Query record"):
        st.json(result)


if view == "Ask / Compare":
    example = st.selectbox("Example questions", ["Write your own", *EXAMPLES])
    question = st.text_area(
        "Ask about the documented architecture",
        value="" if example == "Write your own" else example,
        max_chars=2000,
        height=100,
    )
    mode = st.radio("Retrieval mode", ["Vector", "Graph + Vector", "Compare"], horizontal=True)
    st.caption("Compare runs two independent requests with identical evidence budgets.")
    if st.button("Find evidence and answer", type="primary", disabled=len(question.strip()) < 3):
        modes = (
            ["vector", "graph_vector"]
            if mode == "Compare"
            else ["vector" if mode == "Vector" else "graph_vector"]
        )
        results = []
        for selected in modes:
            with st.spinner(f"Retrieving and generating · {selected}"):
                try:
                    response = httpx.post(
                        f"{API}/ask", json={"question": question, "mode": selected}, timeout=150
                    )
                    if response.is_success:
                        results.append(response.json())
                    else:
                        detail = response.json().get("detail", {})
                        st.error(f"Request failed ({response.status_code}): {detail}")
                except httpx.HTTPError:
                    st.error("API request timed out or failed. Inspect local services.")
        st.session_state["results"] = results
    results = st.session_state.get("results", [])
    if results:
        for col, result in zip(st.columns(len(results)), results, strict=True):
            with col:
                st.subheader("Vector" if result["mode"] == "vector" else "Graph + Vector")
                render(result)
elif view == "Evidence and execution":
    query_id = st.text_input("Query ID")
    if st.button("Load record") and query_id:
        try:
            response = httpx.get(f"{API}/queries/{query_id}", timeout=10)
            if response.is_success:
                render(response.json())
            else:
                st.error("Query record unavailable")
        except httpx.HTTPError:
            st.error("API unavailable")
else:
    reports = sorted(Path("results/runs").glob("*/summary.json"))
    diagnostic = Path("results/development-diagnostic/summary.json")
    if diagnostic.exists():
        reports.insert(0, diagnostic)
    if not reports:
        st.info(
            "No measured benchmark yet. Run the evaluation CLI; human judgments are reported separately."
        )
    else:
        selected_report = st.selectbox(
            "Benchmark run", reports, format_func=lambda p: p.parent.name
        )
        report = json.loads(selected_report.read_text())
        st.json(report)
        st.download_button(
            "Download summary", json.dumps(report, indent=2), "summary.json", "application/json"
        )
